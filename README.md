# The Business Reveal publisher

This repository publishes the prepared five-slide posts to Instagram only. cron-job.org dispatches GitHub Actions automatically at **09:00, 14:00, and 19:00 Europe/Chisinau**. The workflow selects the matching dated post and publishes it through the Meta Graph API.

## Current campaign

- Source calendar: **4–13 October 2026**. Set `CAMPAIGN_START_DATE` to the first live day; the 30 posts then run for ten consecutive days.
- 30 posts, 3 per day, 5 images per post.
- Images are public JPEGs in `assets/`; English captions and exact image order are in `data/posts.json`.
- A missed time slot is not backfilled automatically. Repeated runs of a completed slot are skipped.
- Instagram receives a swipeable carousel. Facebook publishing is disabled.
- Active campaign: **6–15 October 2026**. The IKEA carousel was published on 5 October and will be skipped, leaving 29 posts.
- cron-job.org job `8575393` uses `0 9,14,19 * * *` in Europe/Chisinau. The Python publisher checks the actual local date and time; repeated runs skip published posts. Runs after the 20-minute slot window do not backfill.
- Native GitHub scheduling is disabled. cron-job.org uses a repository-restricted GitHub token with Actions read/write and Metadata read-only. Its dispatch test returned HTTP 204 and GitHub run #8 succeeded outside the publishing slot on 6 October 2026. The first autonomous Instagram publication after this switch is not yet verified.
- The dispatch token expires on 5 December 2026; renew it in cron-job.org before then.
- Meta token expiry has not been verified. If Meta rejects an expired token, update the existing GitHub secret.

## Setup

1. Create a **public** GitHub repository containing this directory's files. Public HTTPS image URLs are needed for Meta to fetch the slides. Keep tokens out of the repository.
2. In repository **Settings → Secrets and variables → Actions**, add these **secrets**:
   - `META_PAGE_ACCESS_TOKEN`: a valid Page access token for the linked Page and professional Instagram account.
   - `META_IG_USER_ID`: the Instagram professional account's numeric ID.
3. Add these **variables**:
   - `MEDIA_BASE_URL`: `https://raw.githubusercontent.com/OWNER/REPO/main` (replace `OWNER` and `REPO`).
   - `CAMPAIGN_START_DATE`: the first publishing date in `YYYY-MM-DD` format, in Chișinău time. Choose a future date when activating the campaign.
   - `PUBLISH_ENABLED`: leave unset until the live connection and first post have been checked. Set to `true` to allow publishing.
4. The Meta app and token need access to the Page and Instagram account, including Instagram content publishing and Page post publishing permissions. The Instagram account must be professional and linked to the Page for the Facebook Login flow.
5. Configure cron-job.org to POST to `https://api.github.com/repos/Ion08/the-business-reveal-autopost/actions/workflows/publish.yml/dispatches` with body `{"ref":"main"}` and an Authorization Bearer header. Keep the token only in cron-job.org, never in this repository. Enable the job after verifying HTTP 204 and the workflow run. Keep `PUBLISH_ENABLED=true` while the campaign should run.

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
