# The Business Reveal publisher

This repository publishes the prepared 30 five-slide posts to Instagram and the linked Facebook Page. A cron-job.org job calls a GitHub Actions workflow at **09:00, 14:00, and 19:00 Europe/Chisinau**. The workflow selects the matching dated post and publishes it through the Meta Graph API.

## Current campaign

- Source calendar: **4–13 October 2026**. Set `CAMPAIGN_START_DATE` to the first live day; the 30 posts then run for ten consecutive days.
- 30 posts, 3 per day, 5 images per post.
- Images are public JPEGs in `assets/`; English captions and exact image order are in `data/posts.json`.
- A missed time slot is not backfilled automatically. Repeated runs of a completed slot are skipped.
- Facebook receives one multi-photo Page post containing all five images. Instagram receives a swipeable carousel.

## Setup

1. Create a **public** GitHub repository containing this directory's files. Public HTTPS image URLs are needed for Meta to fetch the slides. Keep tokens out of the repository.
2. In repository **Settings → Secrets and variables → Actions**, add these **secrets**:
   - `META_PAGE_ACCESS_TOKEN`: a valid Page access token for the linked Page and professional Instagram account.
   - `META_IG_USER_ID`: the Instagram professional account's numeric ID.
   - `META_FB_PAGE_ID`: the Facebook Page's numeric ID.
3. Add these **variables**:
   - `MEDIA_BASE_URL`: `https://raw.githubusercontent.com/OWNER/REPO/main` (replace `OWNER` and `REPO`).
   - `CAMPAIGN_START_DATE`: the first publishing date in `YYYY-MM-DD` format, in Chișinău time. Choose a future date when activating the campaign.
   - `PUBLISH_ENABLED`: leave unset until the live connection and first post have been checked. Set to `true` to allow publishing.
4. The Meta app and token need access to the Page and Instagram account, including Instagram content publishing and Page post publishing permissions. The Instagram account must be professional and linked to the Page for the Facebook Login flow.
5. Create a fine-grained GitHub token with **Actions: Read and write** on this repository only. Keep it in cron-job.org's protected job configuration, not in GitHub or this repository.
6. Create one cron-job.org POST job pointing to `https://api.github.com/repos/OWNER/REPO/actions/workflows/publish.yml/dispatches`. Set timezone `Europe/Chisinau`, hours `09`, `14`, `19`, minute `00`, every day; body `{"ref":"main"}` and headers `Authorization: Bearer <GITHUB_DISPATCH_TOKEN>`, `Accept: application/vnd.github+json`, `Content-Type: application/json`, `X-GitHub-Api-Version: 2022-11-28`.
7. You can instead create that job with `create_cron_job.py` after setting `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_DISPATCH_TOKEN`, and `CRON_JOB_API_KEY` in your local environment. The script creates the job **disabled** for inspection. Enable it only after the GitHub secrets, media URLs, and a dry run are verified.

The cron-job.org API supports a named timezone, so the three local times continue across daylight-saving changes. The job only dispatches GitHub Actions; the Meta token stays in GitHub Secrets.

## Checks

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 publish.py --at 2026-10-04T09:00:00+03:00
```

The date override is dry-run only. The workflow uses the real Chișinău time. No live Meta request occurs when `PUBLISH_ENABLED` is not `true`.

## Duplicate prevention and failures

Before the irreversible Meta publishing call, the workflow commits an `attempting` state for that platform. After Meta returns a media ID, it commits `published`. If the request or its response fails in between, the post remains `attempting` and later runs stop. Check the account in Meta Business Suite and the workflow log before changing state manually. This favors avoiding duplicate public posts over an automatic retry. Instagram and Facebook are tracked independently.

The workflow needs `contents: write` to commit `data/state.json`. Its concurrency group prevents simultaneous runs from publishing the same slot. Do not manually reset an `attempting` record until you have verified whether Meta published it.

## Sources

- [Meta's official Instagram API collection](https://www.postman.com/meta/instagram/folder/9cgqucg/instagram-api-with-facebook-login)
- [Meta's Instagram media publish endpoint](https://www.postman.com/meta/instagram/request/gabnx7r/publish-reel)
- [GitHub workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
- [cron-job.org REST API](https://docs.cron-job.org/rest-api.html)
