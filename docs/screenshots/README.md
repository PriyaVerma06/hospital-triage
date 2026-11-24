# Screenshots

Place screenshots in this folder and reference them from the root README.md.

## Suggested Screenshots

| Filename | What to Capture |
|----------|----------------|
| `login.png` | The login page at `/` |
| `dashboard.png` | Full dashboard with priority queue (red Level-1 patient at top), bed map, and status bar |
| `intake.png` | The intake form filled in for a critical patient |
| `patient-detail.png` | Patient detail drawer/page showing urgency badge (red Level 1) and reason tags |
| `analytics.png` | Analytics page with all 4 charts and KPI cards (after running `python demo.py scenario`) |
| `admin-beds.png` | Admin → Beds tab showing bed list and add-bed modal |
| `alert-toast.png` | Dashboard with an alert toast in the corner |
| `alerts-page.png` | Alerts list page with acknowledge button |
| `history.png` | History page – Patients tab with search/filter active |
| `audit-log.png` | History → Audit Log tab showing clinical event entries |

## How to Take Screenshots

After running `python demo.py scenario --speed fast`:

1. Open Chrome at `http://localhost:5173`
2. Log in as `nurse1` / `demo123`
3. Navigate to each page and use **⌘ + Shift + 4** (macOS) or **Win + Shift + S** (Windows) to capture

Recommended resolution: **1440 × 900** or higher.

> Relative image links in README.md use the form:
> ```markdown
> ![Dashboard](docs/screenshots/dashboard.png)
> ```
