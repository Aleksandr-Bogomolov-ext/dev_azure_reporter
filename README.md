# dats-dev_azure_reporter
Proof-of-Concept for reporting from GitHub Actions to dev.azure.com WorkItems.

This command-line tool allows for updating TaskItems at dev.azure.com from GitHub Actions or GilLab CI/CD via REST API calls. 

## Prerequisites:

  You need a Personal Access Token (PAT). It can be obtained from dev.azure.com, top menu -> User settings -> Personal Access Tokens. 
  Token can be issued for up to a year and can be renewed; token does not need full access to organization and should be created with limited scopes (Scopes -> Custom defined, select "WorkItems Read & write" from the list of available scopes). The token should be stored in GitHub secrets and used from there.

## Usage:
  This tool can be used in two modes:
  
  1. Update a specific TaskItem via its id.
      Parameters:
        - -token - Personal Access Token
        - -project_path - a path to organization and project at dev.azure.com; format: <organization/project>
        - **-task_id** - A TaskItem id from dev.azure.com
        - -field - A name of TaskItem metadata field to write to
        - -value - A value to write to TaskItem metadata field
        - -operation - Either "replace" to erase current field value or "add" to append to it
      
      Example:
      ```
        python dev_azure_reporter.py -token ewopro4r349id4kpdidaksjldas -project_path "digitalfoundation/data-at-scale" -task_id 3712 -field "System.Description" -value "Build was successful" -operation add
      ```
  2. Update a set of TaskItems that match the query: current repository/branch name must be present in a specified field of TaskItem.
    
      Parameters:
        - -token - Personal Access Token
        - -project_path - a path to organization and project at dev.azure.com; format: <organization/project>
        - **-git_path** - a path to a repository and branch where the script is being called from; format: <repository/branch>
        - **-filter_by** - a name of TaskItem metadata field where to look for git_path; only TaskItems that have git_path in this field will be updated
        - **-task_limit** - a maximium count of TaskItems that can be updated by the script; protects from unintentional updating a large number of TaskItems by using a frequently-occurring string in git_path parameter
        - -field - a name of a TaskItem metadata field to write to
        - -value - a value to write to a TaskItem metadata field
        - -operation - either "replace" to erase current TaskItem field value or "add" to append to it
      
      Example:
        ```
        python dev_azure_reporter.py -token ewopro4r349id4kpdidaksjldas -project_path "digitalfoundation/data-at-scale" -git_path "my_repo/this_branch" -filter_by "System.Description" -field "Custom.Securityarchitecturereviewnotes" -value "Security check completed" -op "replace".
        ```
        