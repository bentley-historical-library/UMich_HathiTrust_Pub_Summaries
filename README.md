This script takes a compressed hathitrust metadata file (as downloaded from [here](https://www.hathitrust.org/hathifiles)) and spits out a summary of all
University of Michigan publications found in the file, grouped by publication series.

##Setup
The script requires __python 2.7__ and one third-part python module, __naturalsort__, which you'll need to install this for the program to run. 
Running the following from a command-line prompt should do the trick:

```
pip install naturalsort
```

##Using the script
To use, open a commmand-line prompt, navigate to the script's directory, and run the following

Windows:

```
python .\htpubsummarizer.py C:\path\to\hathitrust\metadata\file\filename.txt.gz
```

Mac:

```
python htpubsummarizer.py /path/to/hathitrust/metadata/file/filename.txt.gz
```

After running for a few minutes it should spit out a file named "summary.csv" in that same directory.


##Notes

###Importing into Excel or Google Sheets
You'd think this would work fine but it turns out both programs are too smart for their own good: some of the enumerations will likely be 
transformed into dates (for example, they will automatically transform the string ```1-5``` into ```1/5/2015```, and some identifiers will also lose their leading zeroes. 
The only way I've found around this is to do the following:

1. Open up excel
2. From the "Data" tab, select "From Text", then choose the csv file
3. You should now see a series of options. First select "Delimited", then click next
4. Uncheck "Tab" and check "Comma", then click next
5. For every trouble column in the csv file, __select that column then click the "text" radio box above__. This forces excel to read the column solely as plain text, and not as anything fancy. The main columns to look out for are the two enumeration columns and the two identifier columns.
6. Once you've done this, click finish and save the file. If you'd like it in google sheets you should now be able to import it directly.

###Enumeration accuracy
The enumeration field as provided by HathiTrust is incredibly messy - turns out if you generalize its possible values there are
a little over 1000 unique formats enumerations can appear in. The script only accounts for the top ten or so most common formats.
Although this does account for a majority of total enumerations, there is still a relatively large amount of data lost
in the long tail of wonky formatting.

So, while the script's enumeration summaries may be useful, they should be taken with a grain of salt.

####Enumeration formats accounted for

_text in brackets is optional. "n" stands for any number; "y" for a number representing a year_

* ```v.n[nn][ yyyy]```
* ```no.n[nn][ yyyy]```
* ```pt.n[nn][ yyyy]```
* ```yyyy[-yyyy]```
* ```yyyy[/yyyy]```
* ```yyyy[-yy]```
* ```yyyy[/yy]```


The following is the only format appearing over 100 times that was not included:

* ```v.nn no.nn``` -- _could not be cleanly summarized_

A full list of possible formats can be found [here](https://goo.gl/CRJYKJ).
