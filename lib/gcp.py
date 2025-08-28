from functools import lru_cache

from google.auth import default
from googleapiclient import discovery


@lru_cache(maxsize=1)
def crm_client():
    credentials, _ = default()
    return discovery.build("cloudresourcemanager", "v3", credentials=credentials)
