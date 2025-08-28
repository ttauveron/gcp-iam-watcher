import urllib.parse


def build_log_url(query: str, update_time: str, scope_key: str, scope_value: str) -> str:
    log_query = urllib.parse.quote(query, safe='')
    log_query = log_query.replace('%28', '%2528')
    log_query = log_query.replace('%29', '%2529')
    log_url_params = f'query={log_query};aroundTime={update_time};duration=PT2M?{scope_key}={scope_value}'
    log_url = f'https://console.cloud.google.com/logs/query;{log_url_params}'
    return log_url


def logs_query_activity(service_name: str, resource_name: str) -> str:
    return (
        'log_id("cloudaudit.googleapis.com/activity")\n'
        f'protoPayload.serviceName="{service_name}"\n'
        f'protoPayload.resourceName:"{resource_name}"'
    )


def logs_query_bucket_adds(bucket_name: str) -> str:
    return (
        'log_id("cloudaudit.googleapis.com/activity")\n'
        'protoPayload.serviceName="storage.googleapis.com"\n'
        'protoPayload.methodName="storage.setIamPermissions"\n'
        f'protoPayload.resourceName="projects/_/buckets/{bucket_name}"\n'
        'protoPayload.serviceData.policyDelta.bindingDeltas.action="ADD"'
    )
