#!/usr/bin/env python3
"""Create one cron-job.org job to dispatch this GitHub workflow daily."""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> int:
    owner = os.environ.get("GITHUB_OWNER")
    repo = os.environ.get("GITHUB_REPO")
    gh_token = os.environ.get("GITHUB_DISPATCH_TOKEN")
    cron_key = os.environ.get("CRON_JOB_API_KEY")
    if not all((owner, repo, gh_token, cron_key)):
        print("Set GITHUB_OWNER, GITHUB_REPO, GITHUB_DISPATCH_TOKEN and CRON_JOB_API_KEY", file=sys.stderr)
        return 1
    workflow_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/publish.yml/dispatches"
    job = {
        "job": {
            "title": "The Business Reveal publisher",
            "url": workflow_url,
            "enabled": False,
            "requestMethod": 1,
            "saveResponses": False,
            "schedule": {
                "timezone": "Europe/Chisinau",
                "expiresAt": 0,
                "hours": [9, 14, 19],
                "minutes": [0],
                "mdays": [-1],
                "months": [-1],
                "wdays": [-1],
            },
            "extendedData": {
                "headers": {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {gh_token}",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                "body": json.dumps({"ref": "main"}),
            },
            "notification": {"onFailure": True, "onFailureCount": 1},
        }
    }
    request = Request(
        "https://api.cron-job.org/jobs",
        data=json.dumps(job).encode("utf-8"),
        method="PUT",
        headers={"Authorization": f"Bearer {cron_key}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        print(f"cron-job.org rejected the job with HTTP {error.code}", file=sys.stderr)
        return 1
    print(f"Created DISABLED cron-job.org job {result['jobId']}; inspect it before enabling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

