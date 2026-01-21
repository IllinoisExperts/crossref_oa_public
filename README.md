# Crossref Open Access and E-publication Program

## Description

This repository contains Python scripts that query the Crossref API for supplemental metadata about Pure research outputs, such as whether a work has a CC license or online publication before print date (e-publication). This information is then written into Pure using the CRUD API. 

## What you need to get started

* **"API Updater.py"** Python script

* **"crossref_data_harvester.py"** Python script

* API key for Production or Staging with read/write permissions for the Research Outputs endpoint (see Administrator > Pure API in the Pure admin interface)

* A __CSV__ file of research outputs with DOI and UUID. (This can be exported as an excel file from Pure--see below--and then re-saved in Excel as a CSV file.)

## A note on exporting from Pure

Each Research output's UUID and DOI must be included in the csv file. If the UUID or DOI is not included in the current export from Pure, navigate to Administrator > Export to Excel > Research outputs and add them to the export configuration (preferrably as some of the first columns).

To export for initial update of existing Research outputs:

* In the Pure backend, navigate to Editor > Research outputs.
* Apply the filter "Electronic Version - DOI" (and select "Has a DOI associated"--The program is not equipped to handle API responses that do not have a DOI present and this will likely cause a fatal error).
* Apply the filter "Visibility" (select "public"--this program will throw a 404 error when attempting to read a restricted item)
* To reduce the potential for timeouts, it is also advisable to limit the size of the export to, e.g., one year's worth of data by applying the "Period" filter. (Depending on the number of outputs in your Pure instance, the program may be able to handle very large lists--up to over 10-20,000--but this will make the program take hours to complete and increases the risks of errors stopping the program before it can complete.)

To export for routine updates of Research outputs:

* In the Pure backend, navigate to Editor > Research outputs.
* Apply the filter "Electronic Version - DOI" (and select "Has a DOI associated"--The program is not equipped to handle API responses that do not have a DOI present and this will likely cause a fatal error).
* Apply the filter "Visibility" (select "public"--this program will throw a 404 error when attempting to read a restricted item)
* Apply the "Period" filter and enter a "Content created date" corresponding with the last run of this program.

## Dependencies

This program requires installing some external python packages. The packages you will need to install include:
* requests
* tqdm
* pandas

If you need helping installing these packages, the following guide may be useful: https://packaging.python.org/en/latest/tutorials/installing-packages/

Many Python integrated development environments (IDEs) also include convenient tools for installing packages. You can look for guides based on your specific IDE, such as this one for PyCharm: https://www.jetbrains.com/help/pycharm/installing-uninstalling-and-upgrading-packages.html

## How to Run

This program is composed of main python script titled **"API Updater.py"** which runs the program and makes the updates to Pure and a custom library titled **"crossref_data_harvester.py"** that defines a function "get_crossref_license_date" that queries the Crossref API for the supplemental metadata. There is no need to run this second program, it will be invoked by "API Updater.py" when that script is run. 

To run the program, download both scripts to the same folder and run **"API Updater.py"** from your integrated development environment (IDE). The program will walk you through the following process:

1. Enter your API key. Press ENTER and the program will automatically move to the next step.

2. Enter the file path of the csv file in a format that is understandable to the program (right click on the file and select "Copy as path" and then paste it into the program console. Make sure the file type extension is also included.)  

3. Enter the URL for the Research Outputs endpoint for your instance of the Pure CRUD (read/write) API (this URL **MUST** include a final "/" or the program will throw 404 errors, e.g. https://experts.illinois.edu/ws/api/research-outputs/). (Please note that the URL will likely be different for the Staging and Production sides of your Pure instance, so be sure you are using the right one while testing the program in Staging to avoid making unwanted changes to the Production side. The API key should also be different, so that will reduce the risk of this happening.)

4. Enter the column header from your CSV file for the column that includes the DOI for each research output.

5. Enter the column header from your CSV file for the column that includes the unique UUID for each research output.

6. Finally, enter the file path for the folder that will hold the error logs once the program completes (right click the folder name and select "Copy as path" and then paste it into the program console.)

## Brief program walkthrough

Once you have entered all of this information, the program will begin to read through the CSV file you indicated and make a GET request for each research output to access the version token in Pure that will allow it to make updates later. 

Next, it will invoke the "get_crossref_license_date" function from the "crossref_data_harvester.py" library to access Crossref's metadata using the DOI of the research output. That function will only retrieve metadata if: 

1. the DOI is found in Crossref's database
2. the agency that registers the DOI is Crossref (e.g. not Datacite or Zenodo)

If these conditions are not met, the program will move on to the next research output and print an error message to the "crossref_errors" txt file in the folder specified earlier. 

If the program is able to successfully retrieve the metadata from Crossref, it will move on to determining which data is relevant. 

The program will retrieve license information only if the Crossref metadata record contains a CC license and the "content-version" under the license is "vor" (version of record). The program will also check if the license start date is later than the current system date when the program is run and add an embargo date to the Pure record set to end on the license start date if this is the case. Otherwise, the OA status on the Pure record will be set to "Open" and the license value from Crossref written in. 

For e-pub ahead of print dates, the program checks if there is already a print publication date on the research output, and if this is the case, whether the e-pub date from Crossref is before or after this print publication date. This is because trying to write an e-pub date that is after a print publication date will throw errors when updating the Pure record. If the e-pub date is after the print date, the e-pub date will be replaced with NONE and not written to the research output. If there is an e-pub date in the Crossref data and all these other checks are confirmed, the date will be written into the Pure record. 

If any relevant changes based on the metadata from Crossref are present, the program will make a final PUT request using json to update the Pure record. Otherwise, if no changes are found, it will skip to the next research output.

If there are no errors while making the requests, you will see the program output a message that the request went through along with the URL for the request (one for the GET request and one for the PUT request). Otherwise, an error message will be printed and written to the error files respectively. Sometimes, there will be 404 errors that look like:
`
"HTTP Error: 404 Client Error: Not Found for url: https://api.crossref.org/works/[DOI here]
Resource not found."
`
This is normal and means the DOI was not found to be valid in Crossref's database. This could mean the DOI is very newly minted and hasn't been indexed yet or the registration agency for the DOI is not Crossref. You can always access these errors later via the "crossref_errors" text file that is generated at the end of the program for further checking or investigation if necessary (**NOTE**: be sure to rename this file if you want to save it before running the program again, or it will be overwritten). 

If, on the other hand, errors are being printed that have the URL of the Pure API rather than the Crossref API, this indicates a more serious issue (either that the program is running into timeout errors, having some problem with updating the Pure record, or the UUIDs in the Excel file are incorrect). These errors will also be accessible in the "put_errors" and "get_errors" txt files alongside the URL for the API call for further investigation. 

A progress bar will also update with each request visualizing the program's progress as it runs. 

## Contact Info
If you have questions or comments about using this program, you can contact the Illinois Experts team at experts-help@illinois.edu
