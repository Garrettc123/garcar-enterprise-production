"""GAR-432: Client-Facing Status Portal
Unique URL per client: /portal/{client_id}
Shows: project status, milestone completion, recent activity, next deliverable, support button.
Pulls data from Linear API + Notion API.
Deploy on Vercel.
"""
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Garcar Client Portal")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_CLIENTS_DB_ID = os.getenv("NOTION_CLIENTS_DB_ID", "")

# Simple client registry (extend with DB in production)
CLIENT_REGISTRY = {
    # "client_id": {"name": "...", "linear_project_id": "...", "notion_page_id": "..."}
}


async def get_linear_project(project_id: str) -> dict:
    query = """
    query GetProject($id: String!) {
      project(id: $id) {
        id name description progress state { name }
        issues { nodes { title state { name } completedAt } }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linear.app/graphql",
            json={"query": query, "variables": {"id": project_id}},
            headers={"Authorization": LINEAR_API_KEY},
            timeout=10,
        )
    data = resp.json()
    return data.get("data", {}).get("project", {})


@app.get("/portal/{client_token}", response_class=HTMLResponse)
async def client_portal(client_token: str):
    client_data = CLIENT_REGISTRY.get(client_token)
    if not client_data:
        raise HTTPException(status_code=404, detail="Portal not found")

    project = {}
    if client_data.get("linear_project_id"):
        project = await get_linear_project(client_data["linear_project_id"])

    progress = project.get("progress", 0)
    issues = project.get("issues", {}).get("nodes", [])
    completed = sum(1 for i in issues if i.get("state", {}).get("name") == "Done")
    total = len(issues)
    next_issue = next(
        (i["title"] for i in issues if i.get("state", {}).get("name") not in ["Done", "Cancelled"]),
        "All milestones complete",
    )

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Garcar — {client_data.get('name', 'Client')} Portal</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #0f0f0f; color: #f0f0f0; margin: 0; padding: 24px; max-width: 600px; }}
    h1 {{ color: #00d4aa; font-size: 1.3rem; }}
    .card {{ background: #1a1a1a; border: 1px solid #333; border-radius: 10px; padding: 16px; margin: 12px 0; }}
    .label {{ font-size: 0.75rem; color: #888; text-transform: uppercase; }}
    .value {{ font-size: 1.2rem; font-weight: 600; color: #fff; margin-top: 4px; }}
    .progress-bar {{ background: #333; border-radius: 4px; height: 8px; margin-top: 8px; }}
    .progress-fill {{ background: #00d4aa; height: 8px; border-radius: 4px; width: {int(progress*100)}%; }}
    .btn {{ display: inline-block; background: #00d4aa; color: #000; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1>Garcar Enterprise — {client_data.get('name', 'Client')} Portal</h1>
  <div class="card">
    <div class="label">Project</div>
    <div class="value">{project.get('name', 'Loading...')}</div>
    <div class="label" style="margin-top:12px">Progress</div>
    <div class="value">{completed}/{total} milestones complete</div>
    <div class="progress-bar"><div class="progress-fill"></div></div>
  </div>
  <div class="card">
    <div class="label">Next Deliverable</div>
    <div class="value">{next_issue}</div>
  </div>
  <div class="card">
    <div class="label">Status</div>
    <div class="value">{project.get('state', {}).get('name', 'In Progress')}</div>
  </div>
  <a href="mailto:gwc2780@gmail.com?subject=Support: {client_data.get('name', 'Client')}" class="btn">Contact Support</a>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/health")
def health():
    return {"status": "ok", "service": "client-portal"}
