# User Manual — Interview Form Summarizer

---

## For Admins

### Getting Started

1. Navigate to your instance URL (e.g. `https://interview.yourdomain.com`)
2. Log in with your admin credentials
3. You'll land on the **Dashboard** — the central hub for managing all interview sessions

---

### Dashboard

The dashboard shows all interview sessions with:
- **Candidate** name
- **Job Title**
- **Template** used
- **Round** (1st, 2nd, 3rd, Final)
- **Progress** (e.g. "2/3 submitted" = 2 of 3 interviewers have submitted)
- **Status** (Pending, Completed, Cancelled)

Click **View** to see session details.

---

### Creating a New Session

1. Click **New Session** on the dashboard
2. Choose how to find the candidate:
   - **Search NocoDB** — type the candidate's name, select from dropdown
   - **Manual Entry** — fill in candidate details directly (for ad-hoc candidates)
3. Select an **Interview Template** (Default, Culture Alignment, HR Interview)
4. Fill in:
   - **Job Title** (auto-fills from NocoDB if available)
   - **Position Applied** (select from list, or "Other" for free text)
   - **Business Unit**
   - **Interview Round**
   - **Interviewer Names** — comma-separated (e.g. "Alice, Bob, Charlie"). Each gets their own unique link.
   - **Interview Date**
   - **Show salary to interviewer** — unchecked by default (you always see salary on the result page)
5. Click **Create Session**
6. Each interviewer gets a unique token link. Share it via Slack, email, WhatsApp, etc.

---

### Viewing Results

1. Click **View** on any session from the dashboard
2. You'll see:
   - **Session Info** — template, job title, round, date, status
   - **Candidate Snapshot** — pulled from NocoDB or manual entry
   - **Interviewers** — each with their status and link (copy button available for pending links)
   - **Assessment Results** — once interviewers submit, their scores appear side-by-side
3. Click **Generate Summary** to trigger the AI summary (only uses tokens when you click)
4. Click **Regenerate Summary** if you want a fresh interpretation (e.g. after a new interviewer submits)
5. Click **Copy as Markdown** to copy the full assessment to clipboard for pasting into Linear, Slack, or docs

---

### Editing a Session

1. Click **Edit Session** on the session detail page
2. You can change: job title, round, interview date, salary visibility, position, business unit
3. You can add new interviewers (comma-separated names) — they get fresh token links
4. Click **Save Changes**

---

### Cancelling a Session

1. On the session detail page, click **Cancel Session** (only available for pending sessions)
2. Confirm the cancellation
3. All interviewer tokens become invalid immediately
4. This action is irreversible

---

### Managing Templates

1. Click **Templates** in the navigation
2. View all available templates and their section count
3. Click **View** to see the sections in a template
4. Click **Set as Default** to change which template is pre-selected on session creation

---

### LLM Settings

1. Click **Settings** in the navigation
2. You can configure:
   - **Base URL** — the LLM endpoint (OpenAI-compatible)
   - **API Key** — masked for security, only updates if you enter a new value
   - **Model** — e.g. `gpt-4o`, `gpt-4o-mini`
   - **System Prompt** — the full instruction for the AI summary generation
3. Changes take effect immediately — no restart needed

---

### Tips

- You only pay for LLM tokens when you click "Generate Summary" — not on interviewer submission
- Multiple interviewers on the same session get a cross-evaluator analysis (convergence/divergence)
- Single interviewer sessions get the standard single-evaluator interpretation
- Salary is always visible to you regardless of the toggle — the toggle only affects what interviewers see

---
---

## For Interviewers

### What You'll Receive

Your admin will share a unique interview assessment link with you. It looks like:
```
https://interview.yourdomain.com/i/aB3xYz...
```

This link is unique to you — no login required.

---

### Filling Out the Assessment

1. Open the link shared with you
2. You'll see a **Candidate Card** at the top with relevant context:
   - Name, position, experience, tech stack, working arrangement
   - (Salary may or may not be visible depending on admin settings)
3. Below that, the assessment sections appear based on the chosen template

---

### Section Types

You may encounter these types of questions:

- **Rating (1-4)** — click one of the numbered buttons. Anchors are shown below (e.g. "1 = No Evidence | 4 = Exceed")
- **Single Select** — pick one option from the list
- **Multi Select** — check up to the allowed number of options (e.g. "Select at most 2")
- **Short Text** — type a brief answer
- **Long Text** — type a longer response

Some sections may appear or disappear based on your previous answers (e.g. selecting "Skip/NOK" may reveal a follow-up question).

---

### Additional Notes

At the bottom of the form, there's an optional **Additional Notes** field. Use it for anything that adds signal beyond the scores — context, observations, caveats.

---

### Consent

Before submitting, you must check the consent box confirming:
- Your evaluation is based on professional judgment
- You consent to data processing and storage
- You acknowledge AI may process your responses to generate a summary

---

### Submitting

1. Ensure all required fields (marked with *) are filled
2. Check the consent checkbox
3. Click **Submit Assessment**
4. You'll see a confirmation page — you can close the tab

---

### Important Notes

- The link is **single-use** — once submitted, you cannot edit or resubmit
- There is no login — the link itself is your access credential
- Do not share your link with others — each interviewer gets their own
- If the session has been cancelled by the admin, you'll see a "cancelled" message when opening the link
