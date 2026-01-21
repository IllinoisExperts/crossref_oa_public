import requests as re
import pandas as pd
from tqdm import tqdm
import json
from crossref_data_harvester import get_crossref_license_date
from urllib.parse import unquote, urlparse
from pathlib import PurePosixPath
import os
from datetime import datetime

def main():
    api_key = input("Enter your API key: ")
    url = input("Enter the URL for the research outputs endpoint of your Pure instance: ")

    file = input("Enter path to file with CSV of research outputs to be updated: ")
    file = file.strip("\"").replace("\\", "/")

    doi_col = input("Enter the name of the column in the csv file that contains the DOI for each output: ")
    uuid_col = input("Enter the name of the column in the csv file that contains the UUID for each output: ")

    while not os.path.isfile(file):
        print(file, 'is not a valid file. Please enter a valid file name (any slashes should be forward slashes and no quotation marks).')
        file = input("Enter the file path to the csv file of research outputs you would like to update: ")
        file = file.strip("\"").replace("\\", "/")


    df = pd.read_csv(file, usecols = [doi_col, uuid_col], encoding = "utf-8-sig", encoding_errors = "replace")
    get_error_count = 0
    put_error_count = 0
    update_count = 0
    license_update_count = 0
    epub_update_count = 0

    out_folder = input("Enter a path where the program should place error logs: ")
    out_folder = out_folder.strip("\"").replace("\\", "/")


    get_errors = open(f"{out_folder}/get_errors.txt", "w+", encoding = "utf-8-sig", errors = "replace")
    put_errors = open(f"{out_folder}/put_errors.txt", "w+", encoding = "utf-8-sig", errors = "replace")

    get_headers = {'accept': 'application/json', 'api-key': api_key}
    put_headers = {'accept': 'application/json', 'api-key': api_key, "content-type": "application/json"}

    '''
    Loop through all records in the CSV file and for each one, make a GET request to the appropriate Pure API instance to retrieve the version string, which
    is the first piece of JSON data that will be written in through later PUT requests. Next retrieve electronic versions data and publication status
    data to be able to write license information and E-Pub dates. Call the external library "crossref_data_harvester" to extract this information from
    CrossRef and write it into the Pure record if certain conditions are met.
    '''

    for i in tqdm(range(len(df))):

        uuid = df[uuid_col][i]
        doi = df[doi_col][i]
        get_response = None
        try:
            get_response = re.get(f"{url}{uuid}", headers = get_headers, timeout = 10)
            get_response.raise_for_status()
        except re.exceptions.HTTPError as errh:
            print(f"Http Error: {errh}")
            get_error_count += 1
            get_errors.write("HTTP Error: " + str(errh) + '\n' + errh.response.text + '\n\n')
        except re.exceptions.ConnectionError as errc:
            print(f"Connection Error: {errc}")
            get_error_count += 1
            get_errors.write("Error Connecting for url: " + f"{url}{uuid}" + "\n" + str(errc) +  '\n\n')
        except re.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
            get_error_count += 1
            get_errors.write("Timeout error for url: " + f"{url}{uuid}" + "\n" + str(errt) +  '\n\n')
        except re.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
            get_error_count += 1
            get_errors.write("Something went wrong: " + str(err) + '\n' + err.response.text + '\n\n')
        else:
            print('get request went through...')
            print(get_response.url)
            get_response_json = get_response.json()
            version = get_response_json.get("version")

            values = {
                "version": version,
            }

            electronic_version = get_response_json["electronicVersions"]
            publication_statuses = get_response_json["publicationStatuses"]

            '''
            Retrieve the print publication date for the Pure record (if there is one) because trying to write in an e-pub date that is 
            later than the print publication date will cause errors. If this is the case, the e-pub date will be overwritten with None and 
            subsequently not be written to the Pure record when the PUT request is made.
            '''

            print_pub_date = None

            for publication_status in publication_statuses:
                if publication_status.get("publicationStatus").get(
                        "uri") == "/dk/atira/pure/researchoutput/status/published":
                    print_pub_date = publication_status["publicationDate"]

            print_pub_string = None
            print_pub_datetime = None

            if print_pub_date is not None:
                if "year" in print_pub_date:
                    if "month" in print_pub_date:
                        if "day" in print_pub_date:
                            print_pub_string = f"{print_pub_date['year']}-{print_pub_date['month']}-{print_pub_date['day']}"
                            print_pub_datetime = datetime.strptime(print_pub_string, "%Y-%m-%d").date()
                        else:
                            print_pub_string = f"{print_pub_date['year']}-{print_pub_date['month']}"
                            print_pub_datetime = datetime.strptime(print_pub_string, "%Y-%m").date()
                    else:
                        print_pub_string = f"{print_pub_date['year']}"
                        print_pub_datetime = datetime.strptime(print_pub_string, "%Y").date()

            crossref_dict = get_crossref_license_date(doi, out_folder)
            license_url = crossref_dict["license"]
            epub_date = crossref_dict["date"]
            embargo = crossref_dict["embargo"]
            changes = False

            if epub_date is not None and print_pub_datetime is not None:

                for format_string in ("%Y, %m, %d", "%Y, %m", "%Y"):
                    try:
                        epub_datetime = datetime.strptime(epub_date, format_string).date()
                        break
                    except ValueError:
                        continue

                if epub_datetime > print_pub_datetime:
                    epub_date = None

            '''
            If there was a license present in the CrossRef data for the version of record, check if it is a CC license. If this is true, 
            parse the license URL to retrieve what kind of license it is. If the license start date was found to be later than today in the external Crossref 
            function call, set the OA status to "Embargoed" with an embargo end date the day the OA license begins. Otherwise, set OA status as "Open."
            '''

            if license_url is not None:
                if urlparse(license_url).netloc == "creativecommons.org":
                    changes = True
                    if embargo is not None:
                        electronic_version[0]["accessType"]["uri"] = "/dk/atira/pure/core/openaccesspermission/embargoed"
                        electronic_version[0]["accessType"]["term"]["en_US"] = "Embargoed"
                        embargo_period = {
                            "endDate": embargo
                        }
                        electronic_version[0]["embargoPeriod"] = embargo_period
                    else:
                        electronic_version[0]["accessType"]["uri"] = "/dk/atira/pure/core/openaccesspermission/open"
                        electronic_version[0]["accessType"]["term"]["en_US"] = "Open"
                    license_code = PurePosixPath(unquote(urlparse(license_url).path)).parts[2].lower()
                    if license_code == "by":
                        uri = "/dk/atira/pure/core/document/licenses/cc_by"
                        term = "CC BY"
                    elif license_code == "by-sa":
                        uri = "/dk/atira/pure/core/document/licenses/cc_by_sa"
                        term = "CC BY-SA"
                    elif license_code == "by-nc":
                        uri = "/dk/atira/pure/core/document/licenses/cc_by_nc"
                        term = "CC BY-NC"
                    elif license_code == "by-nc-sa":
                        uri = "/dk/atira/pure/core/document/licenses/cc_by_nc_sa"
                        term = "CC BY-NC-SA"
                    elif license_code == "by-nd":
                        uri = "/dk/atira/pure/core/document/licenses/cc_by_nd"
                        term = "CC BY-ND"
                    elif license_code == "by-nc-nd":
                        uri = "/dk/atira/pure/core/document/licenses/cc_by_nc_nd"
                        term = "CC BY-NC-ND"
                    elif license_code == "zero" or license_code == "cc0":
                        uri = "/dk/atira/pure/core/document/licenses/cc0"
                        term = "CC0"
                    elif license_code == "mark":
                        uri = "/dk/atira/pure/core/document/licenses/cc_pdm"
                        term = "CC PDM"
                    else:
                        uri = "/dk/atira/pure/core/document/licenses/other"
                        term = "Other"
                    crossref_license = {
                            "uri" : uri,
                            "term": {
                                "en_US" : term,
                            }
                        }
                    electronic_version[0]["licenseType"] = crossref_license
                    values["electronicVersions"] = electronic_version
                    license_update_count += 1


            '''
            Retrieve e-pub date from Crossref data and split it into day, month, and year values. If there is an existing e-pub date in Pure,
            overwrite its values with the Crossref data. If there is not, create a new publication status.
            '''

            if epub_date is not None:
                changes = True
                has_epub = False
                date_list = epub_date.split(", ")
                year = date_list[0]
                month = None
                day = None
                if len(date_list) == 2:
                    month = date_list[1]
                elif len(date_list) == 3:
                    month = date_list[1]
                    day = date_list[2]
                for publication_status in publication_statuses:
                    if publication_status.get("publicationStatus").get("uri") == "/dk/atira/pure/researchoutput/status/epub":
                        has_epub = True
                        if month is not None and day is not None:
                            publication_status["publicationDate"]["year"] = year
                            publication_status["publicationDate"]["month"] = month
                            publication_status["publicationDate"]["day"] = day
                        elif month is not None:
                            if "day" in publication_status["publicationDate"]:
                                publication_status["publicationDate"]["day"] = "null"
                            publication_status["publicationDate"]["year"] = year
                            publication_status["publicationDate"]["month"] = month
                        else:
                            if "day" in publication_status["publicationDate"]:
                                publication_status["publicationDate"]["day"] = "null"
                            if "month" in publication_status["publicationDate"]:
                                publication_status["publicationDate"]["month"] = "null"
                            publication_status["publicationDate"]["year"] = year
                        break
                if has_epub is False:
                    if month is not None and day is not None:
                        new_epub = {
                            "publicationStatus": {
                                "uri": "/dk/atira/pure/researchoutput/status/epub",
                                "term": {
                                    "en_US": "E-pub ahead of print"
                                }
                            },
                            "publicationDate": {
                                "year": year,
                                "month": month,
                                "day": day
                            }
                        }
                    elif month is not None:
                        new_epub = {
                            "current": "false",
                            "publicationStatus": {
                                "uri": "/dk/atira/pure/researchoutput/status/epub",
                                "term": {
                                    "en_US": "E-pub ahead of print"
                                }
                            },
                            "publicationDate": {
                                "year": year,
                                "month": month
                            }
                        }
                    else:
                        new_epub = {
                            "current": "false",
                            "publicationStatus": {
                                "uri": "/dk/atira/pure/researchoutput/status/epub",
                                "term": {
                                    "en_US": "E-pub ahead of print"
                                }
                            },
                            "publicationDate": {
                                "year": year
                            }
                        }
                    publication_statuses.append(new_epub)
                values["publicationStatuses"] = publication_statuses
                epub_update_count += 1

            values = json.dumps(values, indent = 4)

            '''
            If any new data was found, make a PUT request to the appropriate Pure API instance and write said data into Pure.
            '''

            if changes is True:
                put_response = None
                try:
                    put_response = re.put(f"{url}{uuid}", headers=put_headers, data = values, timeout=10)
                    put_response.raise_for_status()
                except re.exceptions.HTTPError as errh:
                    print(f"Something went wrong: {errh}")
                    put_error_count += 1
                    put_errors.write("HTTP Error: " + str(errh) + '\n' + errh.response.text + '\n\n')
                except re.exceptions.ConnectionError as errc:
                    print(f"Something went wrong: {errc}")
                    put_error_count += 1
                    put_errors.write("Error Connecting for url: " + f"{url}{uuid}" + "\n" + str(errc) +  '\n\n')
                except re.exceptions.Timeout as errt:
                    print(f"Something went wrong: {errt}")
                    put_error_count += 1
                    put_errors.write("Timeout error for url: " + f"{url}{uuid}" + "\n" + str(errt) +  '\n\n')
                except re.exceptions.RequestException as err:
                    print(f"Something went wrong: {err}")
                    put_error_count += 1
                    put_errors.write("Something went wrong: " + str(err) + '\n' + err.response.text + '\n\n')
                else:
                    print('put request went through...')
                    print(put_response.url)
                    update_count += 1

    get_errors.write(str(get_error_count) + ' get request errors occurred')
    put_errors.write(str(put_error_count) + ' put request errors occurred')

    put_errors.close()
    get_errors.close()

    with open(f"{out_folder}/exit_report.txt", "w+", encoding = "utf-8-sig", errors = "replace") as exit_report:
        exit_report.write(str(update_count) + " research outputs were updated.\n")
        exit_report.write(str(license_update_count) + " license values were updated.\n")
        exit_report.write(str(epub_update_count) + " epub dates were written.\n")

    print(str(update_count) + " research outputs were updated.")
    print(str(license_update_count) + " license values were updated.")
    print(str(epub_update_count) + " epub dates were written.")




main()


