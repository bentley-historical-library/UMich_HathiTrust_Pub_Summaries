import os
import re
import csv
import json
import gzip
import codecs
import cStringIO
from sys import argv
from operator import itemgetter
from itertools import groupby
from collections import defaultdict

from natsort import natsort


def main():
    filename = "ht_data.json" if len(argv) == 1 else argv[1]

    summarizer = HTPubSummarizer(source_file=filename)
    summarizer.summarize()


class HTPubSummarizer:
    def __init__(self, source_file):
        # these headers must stay in this order - this is the order they are in in the original HT data file
        self.all_hathitrust_headers = ["ht identifier", "access", "rights", "ht record number",
                                       "enumeration/chronology", "source", "source institution record number",
                                       "oclc numbers", "ISBNs", "ISSNs", "LCCNs", "title", "imprint",
                                       "rights determination reason code", "date of last update",
                                       "is government document", "publication date", "publication place", "language",
                                       "bibliographic format"]

        self.data_to_extract = ["ht identifier", "rights", "oclc numbers", "source institution record number", "title",
                               "enumeration/chronology", "imprint", "publication date", "publication place"]

        print("\nLoading data from gzip file. Might take a few minutes...")
        self.data = self._load_data(source_file)

        print("Grouping publications by oclc identifier...")
        # a dictionary in the form
        # {oclc_identifier, publications_with_that_identifier{
        #                       volume_number, publication_dict{
        #                              "row_name": "row value", ...}
        #                       }
        # }
        self.grouped_data = self._group_data_by_id_numbers()


    def summarize(self):
        output = []

        # the columns to be printed out in the output csv file.
        headers = [u"num_of_items", u"oclc identifier", u"source institution identifier", u"source", u"title",
                   u"imprint", u"copyright statuses of publications in series", u"publication date range", u"enumerations",
                   u"missing enumerations", u"earliest publication", u"latest publication"]


        print("Creating summaries...")
        # for every series identified in the hathitrust data
        for oclc_identifier, pubs_dict in self.grouped_data.items():

            # create a data dictionary with default values
            data_dict = self._initialize_series_dict(oclc_identifier)

            # extract basic metadata for the series and collect some item-level metadata for all items in the series
            data_dict.update(self._extract_base_series_metadata(pubs_dict))
            data_dict.update(self._extract_series_item_metadata_lists(pubs_dict))

            # make human-readable summaries for some of the item-level information
            data_dict.update(self._summarize_years(data_dict))
            data_dict.update(self._summarize_copyrights(data_dict))
            data_dict.update(self._summarize_enumerations(data_dict))

            # construct an output row based on the headers designated above, and append that to the output list
            row = self._make_output_row(data_dict, headers)
            output.append(row)

        # write the results
        print("Writing to file...")
        self._write_to_csv(headers, output)

        print("Done!")

    @staticmethod
    def _write_to_csv(headers, output):
        with open("summary.csv", mode="wb") as f:
            output.sort(reverse=True)
            writer = UnicodeWriter(f)
            writer.writerow(headers)
            for row in output:
                try:
                    writer.writerow(row)
                except UnicodeEncodeError as e:
                    print(e)
                    print(row)


    def _summarize_years(self, data_dict):
        d = {}
        if data_dict[u"years"]:
            d[u"humanized_years"] = self._humanize_list(self._summarize_digit_list(sorted(list(data_dict[u"years"]))))
            d[u"earliest publication"] = min(data_dict[u"years"])
            d[u"latest publication"] = max(data_dict[u"years"])
            if len(data_dict[u"years"]) <= 1:
                d[u"publication date range"] = u""
            else:
                d[u"publication date range"] = u"{}-{}".format(d[u"earliest publication"], d[u"latest publication"])

        return d


    def _summarize_copyrights(self, data_dict):
        return {u"copyright statuses of publications in series": self._humanize_list(list(data_dict["copyrights"]))}


    def _summarize_enumerations(self, data_dict):
        enum_regex = re.compile(r"^(?:v|pt|no)\.(\d\d?\d?)[ \d]{0,5}$")
        year_regex = re.compile(r"^(\d{4})[-/]?(\d{2,4})?$")
        enumerations = data_dict[u"enumerations"]
        numbers = set()
        years = set()

        for enumeration in enumerations:
            number = re.findall(enum_regex, enumeration.strip())
            if number:
                numbers.add(int(number[0]))

            year = re.findall(year_regex, enumeration.strip())
            if year:
                year = list(filter(None, year[0]))
                if len(year) == 2:
                    year1, year2 = year
                    if len(year2) == 2:
                        year2 = year1[:2] + year2
                    years.add(int(year1))
                    years.add(int(year2))
                else:
                    years.add(int(year[0]))

        if years and not numbers:
            results = years
        elif numbers:
            results = numbers
        else:
            results = set()

        missing = []
        if results:
            for i in range(min(results), max(results)):
                if i not in results:
                    missing.append(i)

        results = self._humanize_list(self._summarize_digit_list(sorted(list(results))))
        missing = self._humanize_list(self._summarize_digit_list(missing))

        return {u"enumerations": results, u"missing enumerations": missing}


    @staticmethod
    def _make_output_row(data_dict, headers):
        return [data_dict[header] for header in headers]

    @staticmethod
    def _extract_base_series_metadata(pubs_dict):
        d = {u"num_of_items": len(pubs_dict)}

        # since we're only summarizing, we'll just grab info for the first pub in each series
        for volume, pub in pubs_dict.items():
            d[u"title"] = pub[0].get("title", "[no title]")
            d[u"source"] = pub[0].get("ht identifier", "[none].none").split(".")[0]
            d[u"source institution identifier"] = pub[0].get("source institution record number", "[none]")
            d[u"imprint"] = pub[0].get("imprint", "[none]")
            break

        return d

    @staticmethod
    def _extract_series_item_metadata_lists(pubs_dict):
        d = {u"years": set(), u"copyrights": set(), u"enumerations": set()}

        for volume, pubs in pubs_dict.items():
            for pub in pubs:
                year = unicode(pub.get("publication date", ""))
                if year and year != u"9999":
                    d[u"years"].add(int(year))

                if pub.get("rights", ""):
                    d[u"copyrights"].add(unicode(pub.get("rights", "")))

                if pub.get("enumeration/chronology", ""):
                    d[u"enumerations"].add(unicode(pub.get("enumeration/chronology", "")))

        return d


    @staticmethod
    def _initialize_series_dict(oclc_identifier):
        return {u"title": u"[no title]",
                u"contributor": u"[none]",
                u"local_identifier": u"[none]",
                u"imprint": u"[none]",
                u"oclc identifier": oclc_identifier if oclc_identifier else u"[none]",
                u"years": set(),
                u"copyrights": set(),
                u"copyright statuses of publications in series": u"no copyrights",
                u"enumerations": set(),
                u"all publication dates": u"",
                u"earliest publication": u"",
                u"latest publication": u"",
                u"publication date range": u""}


    def _load_data(self, source_file):
        filename, extension = os.path.splitext(source_file)
        if extension == ".json":
            return self._load_data_from_json(source_file)
        elif extension == ".gz":
            return self._load_data_from_ht_gzip_dump(source_file)
        else:
            print("Not a valid input file")
            exit()


    def _load_data_from_ht_gzip_dump(self, path_to_gz_file):
        with gzip.open(path_to_gz_file, mode='rb') as f:
            reader = UnicodeDictReader(f, delimiter="\t", fieldnames=self.all_hathitrust_headers, quoting=csv.QUOTE_NONE)
            return self._facet_by_umich_publisher(reader)


    @staticmethod
    def _load_data_from_json(path_to_json):
        with open(path_to_json, mode="r") as f:
            return json.load(f)


    def _facet_by_umich_publisher(self, reader):
        results = []
        for row in reader:
            if "University of Michigan" not in row.get(u"imprint", u""):
                continue
            results.append(self._extract_relevant_rows(row))

        return results


    def _extract_relevant_rows(self, row):
        return {key: value for (key, value) in row.items() if key in self.data_to_extract}


    def _group_data_by_id_numbers(self):
        grouped_data = defaultdict(lambda: defaultdict(list))
        for pub in self.data:
            identifier = unicode(pub.get("oclc numbers", "")) or u"local (non-oclc): " + unicode(pub["source institution record number"])
            enumeration = unicode(pub.get("enumeration/chronology", "no enumeration value")) or u"no enumeration value"
            grouped_data[identifier][enumeration].append(pub)
        return grouped_data


    @staticmethod
    def _humanize_list(list_or_set):
        list_len = len(list_or_set)

        if list_len == 0:
            return u""

        if list_len == 1:
            return list_or_set[0]

        if list_len == 2:
            return u"{} and {}".format(list_or_set[0], list_or_set[1])

        string = u""
        for i, element in enumerate(list_or_set):
            element = unicode(element)
            if i == list_len - 1:
                string += u"and {}".format(element)
            else:
                string += u"{}, ".format(element)

        return string


    @staticmethod
    def _summarize_digit_list(list_or_set):
        # In some cases there are hundreds of "missing" boxes. To make the output more human-readable, the code below
        # contracts sequential series of missing numbers into a range, e.g. [1, 2, 3, 4] into "1-4"

        # First extract each series of sequential numbers
        # (code from the python docs, see https://docs.python.org/2.6/library/itertools.html#examples)
        range_lists = []
        for k, g in groupby(enumerate(list_or_set), lambda ix: ix[0]-ix[1]):
            range_lists.append(map(itemgetter(1), g))

        # make each sequence human-readable, by grabbing the first and last values of each sequence list
        ranges = []
        for range in range_lists:
            if len(range) > 1:
                ranges.append(u"{0}-{1}".format(range[0], range[-1]))
            elif len(range) == 1:
                ranges.append(unicode(range[0]))

        # Since this is a list of strings that sometimes contain non-numeric characters, we use the naturalsort library to
        # return the results in the expected order. Otherwise ["2-10", "11-19", "20"] would be sorted ["11-19", "2-10", "20"]
        return natsort(ranges)


    @staticmethod
    def _write_data_to_json(filename, json_data):
        with open(filename, mode="w") as f:
            f.write(json.dumps(json_data, sort_keys=True, indent=4, ensure_ascii=False, encoding="utf-8"))


# utility class to correctly write special characters in the output csv file
class UnicodeWriter:
    def __init__(self, f, dialect=csv.excel, encoding="utf-8-sig", **kwds):
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        '''writerow(unicode) -> None
        This function takes a Unicode string and encodes it to the output.
        '''
        self.writer.writerow([s.encode("utf-8") if type(s) == unicode else unicode(s).encode("utf-8") for s in row])
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def UnicodeDictReader(utf8_data, **kwargs):
    csv_reader = csv.DictReader(utf8_data, **kwargs)
    for row in csv_reader:
        yield {key: unicode(value, 'utf-8') for key, value in row.iteritems()}


if __name__ == "__main__":
    main()
