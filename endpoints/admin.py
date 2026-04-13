import logging
from datetime import date, timedelta

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from common.fastapi_server import api
from common.mysql import MySQL as db

logger = logging.getLogger("fastapi")


# ---------------------------------------------------------------------------
# HTML (single template, inline. No Jinja dependency for this small surface.)
# ---------------------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Editron — Access</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #fafafa; color: #1d1d1f;
    margin: 0; padding: 40px 24px; max-width: 1000px; margin: 0 auto;
  }}
  h1 {{ font-weight: 600; letter-spacing: -0.02em; margin: 0 0 32px; }}
  .card {{
    background: #fff; border: 1px solid #e5e5e7; border-radius: 12px;
    padding: 24px; margin-bottom: 24px;
  }}
  h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em;
       color: #86868b; margin: 0 0 16px; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 12px 8px; border-bottom: 1px solid #f0f0f2; font-size: 14px; }}
  th {{ color: #86868b; font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 500; }}
  .badge-active {{ background: #d1f4dd; color: #0a7f34; }}
  .badge-expired {{ background: #fde2e2; color: #b3261e; }}
  form.inline {{ display: inline; }}
  input[type=text], input[type=email], input[type=date] {{
    padding: 8px 12px; border: 1px solid #d2d2d7; border-radius: 8px;
    font-size: 14px; font-family: inherit; width: 100%;
  }}
  .grid {{ display: grid; grid-template-columns: repeat(5, 1fr) auto; gap: 12px; align-items: end; }}
  label {{ font-size: 12px; color: #86868b; display: block; margin-bottom: 4px; }}
  button {{
    padding: 8px 16px; border: none; border-radius: 8px; background: #0071e3;
    color: #fff; font-size: 14px; font-weight: 500; cursor: pointer; font-family: inherit;
  }}
  button:hover {{ background: #0077ed; }}
  button.danger {{ background: transparent; color: #b3261e; padding: 6px 10px; }}
  button.danger:hover {{ background: #fde2e2; }}
  button.ghost {{ background: transparent; color: #0071e3; padding: 6px 10px; }}
  .empty {{ color: #86868b; font-size: 14px; padding: 24px; text-align: center; }}
</style>
</head>
<body>
  <h1>Editron · Access</h1>

  <div class="card">
    <h2>Add user</h2>
    <form method="post" action="/editron/users">
      <div class="grid">
        <div><label>Telegram ID</label><input name="user_id" type="text" required></div>
        <div><label>First name</label><input name="first_name" type="text" required></div>
        <div><label>Last name</label><input name="last_name" type="text"></div>
        <div><label>Email</label><input name="email" type="email"></div>
        <div><label>Expiry</label><input name="expiry_date" type="date" value="{default_expiry}" required></div>
        <div><button type="submit">Add</button></div>
      </div>
    </form>
  </div>

  <div class="card">
    <h2>Users ({count})</h2>
    {rows_html}
  </div>
</body>
</html>
"""

EMPTY = '<div class="empty">No users yet.</div>'

TABLE_HEAD = """
<table>
  <thead><tr>
    <th>Telegram ID</th><th>Name</th><th>Email</th>
    <th>Expiry</th><th>Status</th><th></th>
  </tr></thead>
  <tbody>{body}</tbody>
</table>
"""

ROW = """
<tr>
  <td><code>{user_id}</code></td>
  <td>{first_name} {last_name}</td>
  <td>{email}</td>
  <td>
    <form class="inline" method="post" action="/editron/users/{id}">
      <input name="expiry_date" type="date" value="{expiry_date}" style="width:160px">
      <button type="submit" class="ghost">Update</button>
    </form>
  </td>
  <td>{badge}</td>
  <td>
    <form class="inline" method="post" action="/editron/users/{id}/delete"
          onsubmit="return confirm('Delete {first_name}?');">
      <button type="submit" class="danger">Delete</button>
    </form>
  </td>
</tr>
"""


def _row(u):
    today = date.today()
    active = u["expiry_date"] >= today
    badge = ('<span class="badge badge-active">Active</span>'
             if active else '<span class="badge badge-expired">Expired</span>')
    return ROW.format(
        id=u["id"],
        user_id=u["user_id"],
        first_name=(u["first_name"] or "").replace("<", "&lt;"),
        last_name=(u["last_name"] or "").replace("<", "&lt;"),
        email=(u["email"] or "—").replace("<", "&lt;"),
        expiry_date=u["expiry_date"].isoformat(),
        badge=badge,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api.get("/editron", response_class=HTMLResponse)
@api.get("/editron/", response_class=HTMLResponse)
async def admin_index():
    users = await db.aexecute_query(
        """
        SELECT
            id, user_id,
            first_name, last_name, email,
            expiry_date
        FROM `user`
        ORDER BY
            expiry_date DESC,
            id DESC;
        """
    )

    body = "".join(_row(u) for u in users) if users else ""
    rows_html = TABLE_HEAD.format(body=body) if users else EMPTY

    return PAGE.format(
        rows_html=rows_html,
        count=len(users),
        default_expiry=(date.today() + timedelta(days=30)).isoformat(),
    )


@api.post("/editron/users")
async def admin_create_user(
    user_id: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(""),
    email: str = Form(""),
    expiry_date: str = Form(...),
):
    try:
        await db.aexecute_insert(
            """
            INSERT INTO `user` (
                user_id,
                first_name, last_name, email,
                expiry_date
            )
            VALUES (
                %s,
                %s, %s, %s,
                %s
            )
            ON DUPLICATE KEY UPDATE
                first_name  = VALUES(first_name),
                last_name   = VALUES(last_name),
                email       = VALUES(email),
                expiry_date = VALUES(expiry_date);
            """,
            (
                user_id.strip(),
                first_name.strip(),
                last_name.strip() or None,
                email.strip() or None,
                expiry_date,
            ),
        )
    except Exception as e:
        logger.error(f"admin_create_user failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse("/editron", status_code=303)


@api.post("/editron/users/{user_pk}")
async def admin_update_expiry(user_pk: int, expiry_date: str = Form(...)):
    # Updating expiry clears the notice throttle so the user can be re-notified
    # cleanly if the new date is still in the past.
    await db.aexecute_update(
        """
        UPDATE `user`
        SET
            expiry_date        = %s,
            last_expiry_notice = NULL
        WHERE
            id = %s;
        """,
        (expiry_date, user_pk),
    )
    return RedirectResponse("/editron", status_code=303)


@api.post("/editron/users/{user_pk}/delete")
async def admin_delete_user(user_pk: int):
    await db.aexecute_update(
        """
        DELETE FROM `user`
        WHERE
            id = %s;
        """,
        (user_pk,),
    )
    return RedirectResponse("/editron", status_code=303)