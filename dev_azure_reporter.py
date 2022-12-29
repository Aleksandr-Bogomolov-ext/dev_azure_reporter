import requests
import json
from requests.auth import HTTPBasicAuth
import argparse

BASE_URL = "https://dev.azure.com/#ORG_PROJECT#/_apis/wit/workItems/"

REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Type":"application/json-patch+json"
}

API_VERSION = "7.1-preview"

REQUEST_QUERY_PARAMS = {
    "api-version": API_VERSION
}

REQUIRED_ARGS = {
    "org_project":{
        "description": """
        (required) A path to organization and project at dev.azure.com. Format: "<organization>/<project>".
        """,
        "required": True
    },
    "dev_azure_pat": {
        "description": """
        (required) Personal Access Token (PAT) from dev.azure.com. Token lifespan cannot exceed a year, manual renewal is required.
        """,
        "required": True
    },
    "dev_azure_task_id": {
        "description" : """
        (required) Task numeric identifier from dev.azure.com.
        """,
        "required": True
    },
    "field_name": {
        "description": """
        (Required) A task field to write/replace. *A field that is not included in Work Item layout will be written but will remain invisible.*
        """,
        "required": True
    },
    "operation": {
        "description": """
        (required) An operation to perform on a field. Allowed values: "replace", "add" (appends the field_value to the existing field). Default value is "replace"
        """,
        "required": False,
        "choices": ["add", "replace"],
        "default": "replace"
    },
    "field_value": {
        "description": """
        A value for a field. Can contain unicode characters and html markup.
        """,
        "required": True
    }
}

class DevAzureReporter():
    def __init__(self, org_project:str, base_url:str, token:str) -> None:
        self.org_project = org_project
        self.base_url = base_url.replace("#ORG_PROJECT#", self.org_project)

        self.token = token

    def _read_value(self, task_id:int, value_name:str) -> dict:
        try:
            rslt = requests.get(
                f"{self.base_url}{task_id}",
                headers=REQUEST_HEADERS,
                auth=HTTPBasicAuth("", self.token),
                params=REQUEST_QUERY_PARAMS

            )
            rslt.raise_for_status()
            return rslt.json()["fields"][value_name]
        except KeyError as e:
            return ""
        except Exception as e:
            print(e)
            return 1

    def report(self, task_id:int, field_name:str, operation:str, value:str) -> int:
        data = [{
            "op": operation,
            "path": f"/fields/{field_name}",
            "value": value if operation != "add" else f"{self._read_value(task_id,field_name)}<br>==========<br>{value}"
        }]


        try:
            rslt = requests.patch(
                f"{self.base_url}{task_id}",
                headers=REQUEST_HEADERS,
                auth=HTTPBasicAuth("", self.token),
                params=REQUEST_QUERY_PARAMS,
                data=json.dumps(data)
            )
            rslt.raise_for_status()
        except Exception as e:
            print(e)
            print(f"payload: {json.dumps(data)}")
            return 1
        else:
            print(f"Response HTTP status code: {rslt.status_code}")
            return 0
        


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
 
    for argument_name in REQUIRED_ARGS:
        parser.add_argument(
            f"-{argument_name}", 
            dest=argument_name,
            help=REQUIRED_ARGS[argument_name]["description"],
            required=REQUIRED_ARGS[argument_name]["required"],
            default=REQUIRED_ARGS[argument_name]["default"] if "default" in REQUIRED_ARGS[argument_name] else None,
            choices=REQUIRED_ARGS[argument_name]["choices"] if "choices" in REQUIRED_ARGS[argument_name] else None
        )
 
    args = parser.parse_args()
    reporter = DevAzureReporter(args.org_project, BASE_URL, args.dev_azure_pat)
    
    result = reporter.report(
        args.dev_azure_task_id,
        args.field_name,
        args.operation,
        args.field_value
    )
    
    exit(result)