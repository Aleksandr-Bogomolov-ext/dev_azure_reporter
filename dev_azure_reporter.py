import requests
import json
from requests.auth import HTTPBasicAuth
import argparse

BASE_WORKITEM_URL = "https://dev.azure.com/#ORG_PROJECT#/_apis/wit/workItems/"
BASE_QUERY_URL = "https://dev.azure.com/#ORG_PROJECT#/_apis/wit/wiql"

WORKITEM_REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Type":"application/json-patch+json"
}

QUERY_REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Type":"application/json"
}

WORKITEM_REQUEST_QUERY_PARAMS = {
    "api-version": "7.1-preview"
}

QUERY_REQUEST_QUERY_PARAMS = {
    "api-version": "7.0-preview"
}
COMMAND_LINE_ARGS = {
    "dev_azure_pat": {
        "description": """
        (required) Personal Access Token (PAT) from dev.azure.com. Token lifespan cannot exceed a year, manual renewal is required.
        """,
        "required": True,
        "short_names": ["-token","-pat"]
    },
    "dev_azure_org_project": {
        "description": """
        (Required) Organization/project path at dev.azure.com. Format: "<organization>/<project>".
        """,
        "required": True,
        "short_names": ["-azure_path",]
    },
    "repository_branch": {
        "description": """
        Current repository and branch name. Format: "<repository>/<branch>". If specified, only TaskItems containing <repository>/<branch> in <query_field> metadata field will be updated.
        """,
        "required": False,
        "short_names": ["-git_path",]
    },
    "dev_azure_task_id": {
        "description": """
        Current repository and branch name. If specified, only a TaskItem with this id will be updated.
        """,
        "required": False,
        "short_names": ["-task_id",]
    },
    "query_field": {
        "description": """
        (Required) TaskItems containing <repository>/<branch> in this metadata field will be updated.
        """,
        "required": True,
        "short_names": ["-q",]
    },
    "operation": {
        "description": """
        An operation to perform on a field. Allowed values: "replace", "add" (appends the field_value to the existing field). Default value is "replace"
        """,
        "required": False,
        "choices": ["add", "replace"],
        "default": "replace",
        "short_names": ["-op",]
    },
    "field_name": {
        "description": """
        A name for a TaskItem field to update.
        """,
        "required": True,
        "short_names": ["-field",]
    },
    "field_value": {
        "description": """
        A value for a field. Can contain unicode characters and html markup.
        """,
        "required": True,
        "short_names": ["-val",]
    }
}

class DevAzureReporter():
    def __init__(
        self, 
        dev_azure_org_project:str, 
        repository_branch:str, 
        token:str
    ) -> None:

        self.dev_azure_org_project = dev_azure_org_project
        self.repository_branch = repository_branch
        self.token = token
        self.workitem_url = BASE_WORKITEM_URL.replace("#ORG_PROJECT#", self.dev_azure_org_project)
        self.query_url = BASE_QUERY_URL.replace("#ORG_PROJECT#", self.dev_azure_org_project)

    def _read_value(self, task_id:int, value_name:str) -> dict:
        try:
            rslt = requests.get(
                f"{self.workitem_url}{task_id}",
                headers=WORKITEM_REQUEST_HEADERS,
                auth=HTTPBasicAuth("", self.token),
                params=WORKITEM_REQUEST_QUERY_PARAMS

            )
            rslt.raise_for_status()
            return rslt.json()["fields"][value_name]
        except KeyError as e:
            return ""
        except Exception as e:
            print(e)
            exit(1)
            
    def _find_tasks(self, query_field: str)->list:
        search_data = {
            "query": f"Select [System.Id] From WorkItems Where [{query_field}] Contains '{self.repository_branch}'"
        }  
        try: 
            rslt=requests.post(
                self.query_url,
                headers=QUERY_REQUEST_HEADERS,
                params=QUERY_REQUEST_QUERY_PARAMS,
                auth=HTTPBasicAuth("",self.token),
                data=json.dumps(search_data)
            )
            rslt.raise_for_status()
        except Exception as e:
            print(e)
            print(search_data["query"])
            exit(1)
        else:
            result = [item["id"] for item in rslt.json()['workItems']]
            if len(result) == 0:
                print(f'No tasks have been found (Task field: "{query_field}", required value: "{self.repository_branch}")')

            return result

    def report_batch(self, query_field: str, field_name:str, value:str, operation:str) -> int:
        task_ids = self._find_tasks(query_field)
        for task_id in task_ids:
            self.report(task_id, field_name, value, operation)

    def report(self, task_id:int, field_name:str, value:str, operation:str) -> int:
        data = [{
            "op": operation,
            "path": f"/fields/{field_name}",
            "value": value if operation != "add" else f"{self._read_value(task_id,field_name)}<br>==========<br>{value}"
        }]

        try:
            rslt = requests.patch(
                f"{self.workitem_url}{task_id}",
                headers=WORKITEM_REQUEST_HEADERS,
                auth=HTTPBasicAuth("", self.token),
                params=WORKITEM_REQUEST_QUERY_PARAMS,
                data=json.dumps(data)
            )
            rslt.raise_for_status()
        except Exception as e:
            print(e)
            print(f"payload: {json.dumps(data)}")
            return 1
        else:
            print(f"Response HTTP status code for task #{task_id}: {rslt.status_code}")
            return 0
        


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
 
    for argument_name in COMMAND_LINE_ARGS:
        parser.add_argument(
            f"-{argument_name}", 
            *COMMAND_LINE_ARGS[argument_name]["short_names"],
            dest=argument_name,
            help=COMMAND_LINE_ARGS[argument_name]["description"],
            required=COMMAND_LINE_ARGS[argument_name]["required"],
            default=COMMAND_LINE_ARGS[argument_name]["default"] if "default" in COMMAND_LINE_ARGS[argument_name] else None,
            choices=COMMAND_LINE_ARGS[argument_name]["choices"] if "choices" in COMMAND_LINE_ARGS[argument_name] else None
        )
 
    args = parser.parse_args()

    if (args.dev_azure_task_id == args.repository_branch == None) or (args.dev_azure_task_id and args.repository_branch) :
        print("Please specify either -dev_azure_task_id or -repository_branch")
        exit(1)

    reporter = DevAzureReporter(args.dev_azure_org_project,args.repository_branch, args.dev_azure_pat)

    if args.repository_branch:
        result = reporter.report_batch(
            args.query_field, 
            args.field_name, 
            args.field_value, 
            args.operation
        )
    elif args.dev_azure_task_id:
        result = reporter.report(
            args.dev_azure_task_id,
            args.field_name,
            args.field_value,
            args.operation

        )
    else:
        result = 1
    
    exit(result)