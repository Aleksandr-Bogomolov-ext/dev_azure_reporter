import requests
import json
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectTimeout
import argparse


BASE_WORKITEM_URL = "https://dev.azure.com/#PROJECT_PATH#/_apis/wit/workItems/"
BASE_QUERY_URL = "https://dev.azure.com/#PROJECT_PATH#/_apis/wit/wiql"

WORKITEM_API_VERSION = "7.1-preview"
QUERY_API_VERSION = "7.1-preview"

GIT_PATH_MIN_LENGTH = 10
TASKITEM_QUERY_LIMIT = 1


class DevAzureReporter:
    def __init__(
        self,
        dev_azure_org_project: str,
        token: str,
        taskitem_query_limit: int = TASKITEM_QUERY_LIMIT,
    ) -> None:

        self.dev_azure_org_project = dev_azure_org_project
        self.token = token
        self.workitem_url = BASE_WORKITEM_URL.replace(
            "#PROJECT_PATH#", self.dev_azure_org_project
        )
        self.query_url = BASE_QUERY_URL.replace(
            "#PROJECT_PATH#", self.dev_azure_org_project
        )
        self.taskitem_query_limit = taskitem_query_limit

    def _read_value(self, task_id: int, field_name: str) -> dict:
        """
        This function reads an existing value from the TaskItem.
        Accepts task_id (dev.azure.com TaskItem id) and field_name.
        Returns a value of a field if the field exists or an empty string otherwise.
        """

        url = f"{self.workitem_url}{task_id}"
        try:
            rslt = requests.get(
                url,
                headers={"Accept": "application/json"},
                auth=HTTPBasicAuth("", self.token),
                params={"api-version": WORKITEM_API_VERSION},
                timeout=10,
            )
            rslt.raise_for_status()
            return rslt.json()["fields"][field_name]
        except ConnectTimeout as e:
            print(f"Connection timeout for {url}")
            exit(1)
        except KeyError as e:
            return ""
        except Exception as e:
            print(e)
            exit(1)

    def _git_path_is_valid(self, git_path):
        """
        This function checks if git_path conforms to the following restrictions:
        - overall length is not less than 10 characters;
        - contains no spaces;
        - contains "/" symbol.

        The purpose of this check is a reduction of a possible false positives
        in _find_tasks - if git_path contains some generic string (or a single letter),
        _find_tasks will return TaskItems that were not intended to be modified by
        this script.

        Returns True if git_path is valid or False otherwise
        """
        if "/" not in git_path:
            return False
        if " " in git_path:
            return False
        if len(git_path) < GIT_PATH_MIN_LENGTH:
            return False

        return True

    def _find_tasks(self, query_field: str, git_path: str) -> list:
        """
        This function performs a search for TaskItems that contain git_path in their metadata field specified in query_field.
        Returns a list of matching TaskItems ids
        """
        if not self._git_path_is_valid(git_path):
            print(
                """
            git_path is invalid. Please make sure it has the 
            following format: "<repository_name>/<branch_name>"
            """
            )
            exit(1)

        search_data = {
            "query": f"Select [System.Id] From WorkItems Where [{query_field}] Contains '{git_path}'"
        }
        try:
            rslt = requests.post(
                self.query_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                auth=HTTPBasicAuth("", self.token),
                params={"api-version": QUERY_API_VERSION},
                data=json.dumps(search_data),
                timeout=10,
            )
            rslt.raise_for_status()
        except ConnectTimeout as e:
            print(f"Connection timeout for {self.query_url}")
            exit(1)
        except Exception as e:
            print(e)
            print(search_data["query"])
            exit(1)
        else:
            result = [item["id"] for item in rslt.json()["workItems"]]

            if len(result) > self.taskitem_query_limit:
                print(
                    f"""
                Too much TaskItems have been found: {len(result)}, limit {self.taskitem_query_limit}. 
                """
                )
                exit(1)
            if len(result) == 0:
                print(
                    f'No TaskItems have been found (Task field: "{query_field}", required value: "{git_path}")'
                )

            return result

    def report_batch(
        self,
        query_field: str,
        git_path: str,
        field_name: str,
        value: str,
        operation: str,
    ) -> int:
        """
        This function performs an update of all the TaskItems that match the criterion:
        A field of TaskItem (query_field) must contain a name of a current repository and branch (git_path).
        Matching TaskItems are updated: a field specified in field_name parameter is being either overwritten
        with value if operation is "replace" or appended with value if operation is "add".
        Returns 0 if all update operations were successful or 1 otherwise.
        """

        task_ids = self._find_tasks(query_field, git_path)
        results = [
            self.report(task_id, field_name, value, operation) for task_id in task_ids
        ]

        return 0 if set(results) == {0} else 1

    def report(self, task_id: int, field_name: str, value: str, operation: str) -> int:
        """
        This function performs update of a single TaskItem at dev.azure.com
        Parameters: task_id, field_name (where to write to), value (what to write)
        and operation (add to existing field value or replace it).
        Returns 0 if operation was successful or 1 otherwise.
        """
        data = [
            {
                "op": operation,
                "path": f"/fields/{field_name}",
                "value": value
                if operation != "add"
                else f"{self._read_value(task_id,field_name)}<br>==========<br>{value}",
            }
        ]
        url = f"{self.workitem_url}{task_id}"
        try:
            rslt = requests.patch(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json-patch+json",
                },
                auth=HTTPBasicAuth("", self.token),
                params={"api-version": WORKITEM_API_VERSION},
                data=json.dumps(data),
                timeout=10,
            )
            rslt.raise_for_status()
        except ConnectTimeout as e:
            print(f"Connection timeout for {url}")
            exit(1)
        except Exception as e:
            print(e)
            print(f"payload: {json.dumps(data)}")
            return 1
        else:
            print(f"Response HTTP status code for task #{task_id}: {rslt.status_code}")
            return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-token",
        required=True,
        help="""
        Personal Access Token (PAT) from dev.azure.com. Token lifespan cannot exceed a year, manual renewal is required.
    """,
    )
    parser.add_argument(
        "-project",
        "-project_path",
        required=True,
        dest="project_path",
        help="""
        Organization/project path at dev.azure.com. Format: "<organization>/<project>".
    """,
    )
    parser.add_argument(
        "-task_id",
        required=False,
        help="""
        Target task id. If specified, only a TaskItem with this id will be updated. 
        Cannot be used with <git_path> and <filter_by> parameters.
    """,
    )
    parser.add_argument(
        "-git_path",
        required=False,
        help=f"""
        Current repository and branch name. Format: "<repository>/<branch>". 
        If specified, only TaskItems containing <git_path> in <filter_by> will be updated.
        If a number of matching TaskItems exceeds a limit ({TASKITEM_QUERY_LIMIT}), the script will fail.
        A limit can be specified via <task_limit> parameter. 
        Cannot be used with <task_id> parameter.
    """,
    )
    parser.add_argument(
        "-filter_by",
        required=False,
        help="""
        If specified, only TaskItems containing <git_path> in <filter_by> field will be updated. 
        Cannot be used with <task_id> parameter.
    """,
    )
    parser.add_argument(
        "-task_limit",
        required=False,
        default=TASKITEM_QUERY_LIMIT,
        help="""
        If specified, the parameter overrides the default limit of the number of TaskItems
        that can be updated by the script. This parameter can be used with <git_path> and <filter_by> parameters. 
        Cannot be used with <task_id> parameter.
    """,
    )
    parser.add_argument(
        "-field_name",
        "-field",
        dest="field_name",
        required=True,
        help="""
        A name of a TaskItem field to write <field_value> to.
    """,
    )
    parser.add_argument(
        "-field_value",
        "-value",
        "-val",
        dest="field_value",
        required=True,
        help="""
        A value for a field. Can contain unicode characters and html markup.
    """,
    )
    parser.add_argument(
        "-operation",
        "-op",
        dest="operation",
        choices=["replace", "add"],
        default="replace",
        required=False,
        help="""
        An operation to perform on a field. 
        Allowed values: "replace", "add" (appends the field_value to the existing field). Default value is "replace".
    """,
    )

    args = parser.parse_args()

    reporter = DevAzureReporter(args.project_path, args.token, args.task_limit)

    # depending on parameters, either update a single TaskItem by task_id or many TaskItems that match the search criterion
    if args.task_id and (args.filter_by == args.git_path == None):
        result = reporter.report(
            args.task_id, args.field_name, args.field_value, args.operation
        )
    elif (args.filter_by and args.git_path) and args.task_id is None:
        result = reporter.report_batch(
            args.filter_by,
            args.git_path,
            args.field_name,
            args.field_value,
            args.operation,
        )
    else:
        print(
            "Please either specify a single task via <task_id> or search criterion via <git_path> and <filter_by>."
        )
        result = 1

    exit(result)