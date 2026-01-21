import requests as re
from datetime import datetime


def get_crossref_license_date(doi: str, out_folder: str) -> dict:

    """
    Returns a dictionary with CrossRef data for license, e-pub date, and embargo value
    """

    response_dict = {"license": None, "date": None, "embargo": None}

    headers = {"accept": "application/json"}

    doi = re.utils.quote(doi, safe = "")

    '''
    Make a GET request to CrossRef API to check that the DOI for the Pure RO is a CrossRef DOI. If it is not, write this to an error file. 
    Otherwise, continue with the next GET request.
    '''

    crossref_errors = open(f"{out_folder}/crossref_errors.txt", "a", encoding = "utf-8-sig", errors = "replace")
    response = None
    agency_response = None
    try:
        agency_response = re.get(f"https://api.crossref.org/works/{doi}/agency", headers = headers, timeout = 10)
        agency_response.raise_for_status()
    except re.exceptions.HTTPError as errh:
        print("HTTP Error: " + str(errh) + '\n' + errh.response.text + '\n\n')
        crossref_errors.write("HTTP Error: " + str(errh) + '\n' + errh.response.text + '\n\n')
    except re.exceptions.ConnectionError as errc:
        print("Error Connecting for url: " + f"https://api.crossref.org/works/{doi}/agency" + "\n" + str(errc) +  '\n\n')
        crossref_errors.write("Error Connecting for url: " + f"https://api.crossref.org/works/{doi}/agency" + "\n" + str(errc) +  '\n\n')
    except re.exceptions.Timeout as errt:
        print("Timeout Error for url: " + f"https://api.crossref.org/works/{doi}/agency" + "\n" + str(errt) +  '\n\n')
        crossref_errors.write("Timeout error for url: " + f"https://api.crossref.org/works/{doi}/agency" + "\n" + str(errt) +  '\n\n')
    except re.exceptions.RequestException as err:
        print("Something went wrong: " + str(err) + '\n' + err.response.text + '\n\n')
        crossref_errors.write("Something went wrong: " + str(err) + '\n' + err.response.text + '\n\n')
    else:
        agency_response_json = agency_response.json()
        if agency_response_json["message"]["agency"]["id"] == "crossref":
            try:
                response = re.get(f"https://api.crossref.org/works/{doi}", headers=headers, timeout=10)
                response.raise_for_status()
            except re.exceptions.HTTPError as errh:
                print("HTTP Error: " + str(errh) + '\n' + errh.response.text + '\n\n')
                crossref_errors.write("HTTP Error: " + str(errh) + '\n' + errh.response.text + '\n\n')
            except re.exceptions.ConnectionError as errc:
                print("Error Connecting for url: " + f"https://api.crossref.org/works/{doi}" + "\n" + str(errc) +  '\n\n')
                crossref_errors.write("Error Connecting for url: " + f"https://api.crossref.org/works/{doi}" + "\n" + str(errc) +  '\n\n')
            except re.exceptions.Timeout as errt:
                print("Timeout Error for url: " + f"https://api.crossref.org/works/{doi}" + "\n" + str(errt) +  '\n\n')
                crossref_errors.write("Timeout Error for url: " + f"https://api.crossref.org/works/{doi}" + "\n" + str(errt) +  '\n\n')
            except re.exceptions.RequestException as err:
                print("Something went wrong: " + str(err) + '\n' + err.response.text + '\n\n')
                crossref_errors.write("Something went wrong: " + str(err) + '\n' + err.response.text + '\n\n')
            else:
                response_json = response.json()
                '''
                Access "published-online" key within the json response object. 
                '''
                epub = response_json.get("message").get("published-online")
                if epub is not None:
                    epub_date = str(epub["date-parts"]).strip("[]")
                    response_dict["date"] = epub_date
                '''
                Access "license" key within the json response object and set an embargo date if the license start date is after today.
                '''
                licenses = response_json.get("message").get("license")
                if licenses is not None:
                    for this_license in licenses:
                        if this_license.get("content-version") == "vor":
                            vor_license = str(this_license.get("URL"))
                            license_start = str(this_license.get("start").get("date-parts")).strip("[]")
                            for format_string in ("%Y, %m, %d", "%Y, %m", "%Y"):
                                try:
                                    license_start = datetime.strptime(license_start, format_string).date()
                                    break
                                except ValueError:
                                    continue
                            if license_start > datetime.today().date():
                                license_start = datetime.strftime(license_start, "%Y-%m-%d")
                                response_dict["embargo"] = license_start
                            response_dict["license"] = vor_license
                            break
        else:
            crossref_errors.write(f"{doi} is not a CrossRef DOI" + '\n\n')

    crossref_errors.close()

    return response_dict
