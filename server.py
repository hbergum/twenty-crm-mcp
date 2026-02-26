"""Twenty CRM MCP Server - Python/FastMCP implementation.

Provides search, CRUD, and note/task target linking for Twenty CRM v1.18.1.
"""

import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

API_KEY = os.environ["TWENTY_API_KEY"]
BASE_URL = os.environ.get("TWENTY_BASE_URL", "http://localhost:3000")
REST = f"{BASE_URL}/rest"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

mcp = FastMCP(
    "Twenty CRM",
    instructions=(
        "Twenty CRM server for managing people, companies, notes, tasks, and opportunities. "
        "Use search_people/search_companies with a query string to find records. "
        "Use create_note/create_task with personIds/companyIds to link them to people/companies. "
        "Use search_opportunities/list_opportunities to find deals/opportunities."
    ),
)

client = httpx.Client(headers=HEADERS, timeout=30)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None) -> dict:
    """GET request to Twenty REST API."""
    r = client.get(f"{REST}/{path}", params=params or {})
    r.raise_for_status()
    return r.json()


def _post(path: str, data: dict) -> dict:
    """POST request to Twenty REST API."""
    r = client.post(f"{REST}/{path}", json=data)
    r.raise_for_status()
    return r.json()


def _patch(path: str, data: dict) -> dict:
    """PATCH request to Twenty REST API."""
    r = client.patch(f"{REST}/{path}", json=data)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    """DELETE request to Twenty REST API."""
    r = client.delete(f"{REST}/{path}")
    r.raise_for_status()
    return r.json()


def _search_objects(object_path: str, query: str, limit: int = 10) -> list[dict]:
    """Search objects using searchVector[like] filter with cursor pagination."""
    results = []
    params = {
        "filter": f"searchVector[like]:%{query.lower()}%",
        "limit": str(min(limit, 60)),
    }
    while len(results) < limit:
        data = _get(object_path, params)
        page_info = data.get("pageInfo", {})
        # The data key is the plural object name (people, companies, etc.)
        for key in data.get("data", {}):
            items = data["data"][key]
            results.extend(items)
            break
        if not page_info.get("hasNextPage"):
            break
        params["starting_after"] = page_info["endCursor"]
    return results[:limit]


def _format_person(p: dict) -> str:
    """Format a person record as readable text."""
    name = p.get("name", {})
    full = f"{name.get('firstName', '')} {name.get('lastName', '')}".strip()
    emails = p.get("emails", {})
    email = emails.get("primaryEmail", "") if isinstance(emails, dict) else ""
    phones = p.get("phones", {})
    phone = ""
    if isinstance(phones, dict):
        cc = phones.get("primaryPhoneCallingCode", "")
        num = phones.get("primaryPhoneNumber", "")
        phone = f"{cc}{num}" if num else ""
    job = p.get("jobTitle", "") or ""
    city = p.get("city", "") or ""
    company_id = p.get("companyId", "") or ""
    parts = [f"**{full}** (id: `{p['id']}`)"]
    if job:
        parts.append(f"  Stilling: {job}")
    if email:
        parts.append(f"  E-post: {email}")
    if phone:
        parts.append(f"  Telefon: {phone}")
    if city:
        parts.append(f"  By: {city}")
    if company_id:
        parts.append(f"  Bedrift-ID: `{company_id}`")
    return "\n".join(parts)


def _format_company(c: dict) -> str:
    """Format a company record as readable text."""
    name = c.get("name", "")
    domain = c.get("domainName", {})
    domain_url = domain.get("primaryLinkUrl", "") if isinstance(domain, dict) else ""
    addr = c.get("address", {})
    city = addr.get("addressCity", "") if isinstance(addr, dict) else ""
    employees = c.get("employees", None)
    icp = c.get("idealCustomerProfile", False)
    parts = [f"**{name}** (id: `{c['id']}`)"]
    if domain_url:
        parts.append(f"  Domene: {domain_url}")
    if city:
        parts.append(f"  By: {city}")
    if employees:
        parts.append(f"  Ansatte: {employees}")
    if icp:
        parts.append(f"  ICP: Ja")
    return "\n".join(parts)


def _format_note(n: dict) -> str:
    """Format a note record."""
    title = n.get("title", "(uten tittel)")
    body_v2 = n.get("bodyV2", {})
    markdown = ""
    if isinstance(body_v2, dict):
        markdown = body_v2.get("markdown", "") or ""
    created = n.get("createdAt", "")[:10]
    parts = [f"**{title}** (id: `{n['id']}`, opprettet: {created})"]
    if markdown:
        # Show first 500 chars of body
        preview = markdown[:500]
        if len(markdown) > 500:
            preview += "..."
        parts.append(preview)
    return "\n".join(parts)


def _format_task(t: dict) -> str:
    """Format a task record."""
    title = t.get("title", "(uten tittel)")
    status = t.get("status", "")
    due = t.get("dueAt", "") or ""
    body_v2 = t.get("bodyV2", {})
    markdown = ""
    if isinstance(body_v2, dict):
        markdown = body_v2.get("markdown", "") or ""
    created = t.get("createdAt", "")[:10]
    parts = [f"**{title}** (id: `{t['id']}`, status: {status}, opprettet: {created})"]
    if due:
        parts.append(f"  Frist: {due[:10]}")
    if markdown:
        preview = markdown[:500]
        if len(markdown) > 500:
            preview += "..."
        parts.append(preview)
    return "\n".join(parts)


def _format_opportunity(o: dict) -> str:
    """Format an opportunity record."""
    name = o.get("name", "(uten navn)")
    stage = o.get("stage", "")
    close_date = o.get("closeDate", "") or ""
    company_id = o.get("companyId", "") or ""
    contact_id = o.get("pointOfContactId", "") or ""
    created = o.get("createdAt", "")[:10]
    # Amount is stored as amountMicros in a currency object
    amount_obj = o.get("amount", {}) or {}
    amount_micros = amount_obj.get("amountMicros") if isinstance(amount_obj, dict) else None
    currency = amount_obj.get("currencyCode", "NOK") if isinstance(amount_obj, dict) else "NOK"
    parts = [f"**{name}** (id: `{o['id']}`, stage: {stage}, opprettet: {created})"]
    if amount_micros is not None:
        amount_nok = amount_micros / 1_000_000
        parts.append(f"  Beløp: {amount_nok:,.2f} {currency}")
    if close_date:
        parts.append(f"  Lukkedato: {close_date[:10]}")
    if company_id:
        parts.append(f"  Bedrift-ID: `{company_id}`")
    if contact_id:
        parts.append(f"  Kontakt-ID: `{contact_id}`")
    return "\n".join(parts)


def _get_targets(target_type: str, parent_id_field: str, parent_id: str) -> list[dict]:
    """Get noteTargets or taskTargets for a given note/task ID.

    Returns a list of targets. Since the REST API doesn't return personId/companyId
    directly for MORPH_RELATION fields, we need to look at each target individually.
    For now, we return what we can get from the list endpoint.
    """
    params = {
        "filter": f"{parent_id_field}[eq]:{parent_id}",
        "limit": "50",
    }
    data = _get(target_type, params)
    for key in data.get("data", {}):
        return data["data"][key]
    return []


# ---------------------------------------------------------------------------
# People tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_people(query: str, limit: int = 10) -> str:
    """Search for people by name, email, job title, or any text field.

    Args:
        query: Search text (name, email, etc.)
        limit: Max results (default 10)
    """
    people = _search_objects("people", query, limit)
    if not people:
        return f"Ingen personer funnet for '{query}'."
    lines = [f"Fant {len(people)} person(er) for '{query}':\n"]
    for p in people:
        lines.append(_format_person(p))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_person(id: str) -> str:
    """Get detailed information about a person.

    Args:
        id: Person UUID
    """
    data = _get(f"people/{id}")
    p = data["data"]["person"]
    return _format_person(p)


@mcp.tool()
def create_person(
    firstName: str,
    lastName: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    jobTitle: Optional[str] = None,
    city: Optional[str] = None,
    companyId: Optional[str] = None,
) -> str:
    """Create a new person in Twenty CRM.

    Args:
        firstName: First name
        lastName: Last name
        email: Email address
        phone: Phone number
        jobTitle: Job title
        city: City
        companyId: Company UUID to link to
    """
    body: dict = {
        "name": {"firstName": firstName, "lastName": lastName},
    }
    if email:
        body["emails"] = {"primaryEmail": email}
    if phone:
        body["phones"] = {
            "primaryPhoneNumber": phone,
            "primaryPhoneCountryCode": "NO",
            "primaryPhoneCallingCode": "+47",
        }
    if jobTitle:
        body["jobTitle"] = jobTitle
    if city:
        body["city"] = city
    if companyId:
        body["companyId"] = companyId
    data = _post("people", body)
    p = data["data"]["createPerson"]
    return f"Person opprettet: {_format_person(p)}"


@mcp.tool()
def update_person(
    id: str,
    firstName: Optional[str] = None,
    lastName: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    jobTitle: Optional[str] = None,
    city: Optional[str] = None,
    companyId: Optional[str] = None,
) -> str:
    """Update an existing person.

    Args:
        id: Person UUID
        firstName: New first name
        lastName: New last name
        email: New email
        phone: New phone
        jobTitle: New job title
        city: New city
        companyId: New company UUID
    """
    body: dict = {}
    if firstName or lastName:
        name = {}
        if firstName:
            name["firstName"] = firstName
        if lastName:
            name["lastName"] = lastName
        body["name"] = name
    if email:
        body["emails"] = {"primaryEmail": email}
    if phone:
        body["phones"] = {
            "primaryPhoneNumber": phone,
            "primaryPhoneCountryCode": "NO",
            "primaryPhoneCallingCode": "+47",
        }
    if jobTitle:
        body["jobTitle"] = jobTitle
    if city:
        body["city"] = city
    if companyId:
        body["companyId"] = companyId
    if not body:
        return "Ingen felter a oppdatere."
    data = _patch(f"people/{id}", body)
    p = data["data"]["updatePerson"]
    return f"Person oppdatert: {_format_person(p)}"


# ---------------------------------------------------------------------------
# Companies tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_companies(query: str, limit: int = 10) -> str:
    """Search for companies by name or other text fields.

    Args:
        query: Search text
        limit: Max results (default 10)
    """
    companies = _search_objects("companies", query, limit)
    if not companies:
        return f"Ingen bedrifter funnet for '{query}'."
    lines = [f"Fant {len(companies)} bedrift(er) for '{query}':\n"]
    for c in companies:
        lines.append(_format_company(c))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_company(id: str) -> str:
    """Get detailed information about a company.

    Args:
        id: Company UUID
    """
    data = _get(f"companies/{id}")
    c = data["data"]["company"]
    return _format_company(c)


@mcp.tool()
def create_company(
    name: str,
    domainName: Optional[str] = None,
    address: Optional[str] = None,
    employees: Optional[int] = None,
    city: Optional[str] = None,
) -> str:
    """Create a new company in Twenty CRM.

    Args:
        name: Company name
        domainName: Company website domain
        address: Street address
        employees: Number of employees
        city: City
    """
    body: dict = {"name": name}
    if domainName:
        body["domainName"] = {"primaryLinkUrl": domainName}
    if address or city:
        addr = {}
        if address:
            addr["addressStreet1"] = address
        if city:
            addr["addressCity"] = city
        body["address"] = addr
    if employees:
        body["employees"] = employees
    data = _post("companies", body)
    c = data["data"]["createCompany"]
    return f"Bedrift opprettet: {_format_company(c)}"


@mcp.tool()
def update_company(
    id: str,
    name: Optional[str] = None,
    domainName: Optional[str] = None,
    address: Optional[str] = None,
    employees: Optional[int] = None,
    city: Optional[str] = None,
) -> str:
    """Update an existing company.

    Args:
        id: Company UUID
        name: New company name
        domainName: New domain
        address: New address
        employees: New employee count
        city: New city
    """
    body: dict = {}
    if name:
        body["name"] = name
    if domainName:
        body["domainName"] = {"primaryLinkUrl": domainName}
    if address or city:
        addr = {}
        if address:
            addr["addressStreet1"] = address
        if city:
            addr["addressCity"] = city
        body["address"] = addr
    if employees:
        body["employees"] = employees
    if not body:
        return "Ingen felter a oppdatere."
    data = _patch(f"companies/{id}", body)
    c = data["data"]["updateCompany"]
    return f"Bedrift oppdatert: {_format_company(c)}"


# ---------------------------------------------------------------------------
# Notes tools
# ---------------------------------------------------------------------------

@mcp.tool()
def create_note(
    title: str,
    body: str,
    personIds: Optional[list[str]] = None,
    companyIds: Optional[list[str]] = None,
) -> str:
    """Create a note and optionally link it to people and/or companies.

    Use format 'Meeting FirstName LastName DD.MM.YY' for meeting note titles.

    Args:
        title: Note title
        body: Note content (markdown)
        personIds: List of person UUIDs to link the note to
        companyIds: List of company UUIDs to link the note to
    """
    note_data = {
        "title": title,
        "bodyV2": {"markdown": body},
    }
    resp = _post("notes", note_data)
    note = resp["data"]["createNote"]
    note_id = note["id"]

    # Create noteTargets for persons
    linked = []
    for pid in (personIds or []):
        try:
            _post("noteTargets", {"noteId": note_id, "targetPersonId": pid})
            linked.append(f"person `{pid}`")
        except Exception as e:
            linked.append(f"person `{pid}` (FEIL: {e})")

    # Create noteTargets for companies
    for cid in (companyIds or []):
        try:
            _post("noteTargets", {"noteId": note_id, "targetCompanyId": cid})
            linked.append(f"bedrift `{cid}`")
        except Exception as e:
            linked.append(f"bedrift `{cid}` (FEIL: {e})")

    result = f"Note opprettet: **{title}** (id: `{note_id}`)"
    if linked:
        result += f"\nKoblet til: {', '.join(linked)}"
    return result


@mcp.tool()
def delete_note(id: str) -> str:
    """Delete a note by its UUID.

    Args:
        id: Note UUID
    """
    resp = _delete(f"notes/{id}")
    deleted_id = resp["data"]["deleteNote"]["id"]
    return f"Note slettet (id: `{deleted_id}`)"


@mcp.tool()
def list_notes(search: Optional[str] = None, limit: int = 20) -> str:
    """List notes, optionally filtered by search text.

    Args:
        search: Search text to filter notes
        limit: Max results (default 20)
    """
    if search:
        notes = _search_objects("notes", search, limit)
    else:
        data = _get("notes", {"limit": str(limit)})
        notes = data["data"]["notes"]
    if not notes:
        return "Ingen notater funnet."
    lines = [f"Fant {len(notes)} notat(er):\n"]
    for n in notes:
        lines.append(_format_note(n))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_note(id: str) -> str:
    """Get a note with full details and linked targets.

    Args:
        id: Note UUID
    """
    data = _get(f"notes/{id}")
    n = data["data"]["note"]
    result = _format_note(n)

    # Get linked targets
    targets = _get_targets("noteTargets", "noteId", id)
    if targets:
        result += f"\n\nKoblede mål ({len(targets)} stk): Se note-targets for detaljer."
    return result


@mcp.tool()
def delete_note(id: str) -> str:
    """Delete a note.

    Args:
        id: Note UUID
    """
    data = _delete(f"notes/{id}")
    return f"Note slettet (id: `{id}`)"


# ---------------------------------------------------------------------------
# Tasks tools
# ---------------------------------------------------------------------------

@mcp.tool()
def create_task(
    title: str,
    body: Optional[str] = None,
    status: Optional[str] = "TODO",
    dueAt: Optional[str] = None,
    personIds: Optional[list[str]] = None,
    companyIds: Optional[list[str]] = None,
) -> str:
    """Create a task and optionally link it to people and/or companies.

    Args:
        title: Task title
        body: Task description (markdown)
        status: Status: TODO, IN_PROGRESS, or DONE (default: TODO)
        dueAt: Due date in ISO 8601 format (e.g. 2026-03-15)
        personIds: List of person UUIDs to link the task to
        companyIds: List of company UUIDs to link the task to
    """
    task_data: dict = {"title": title}
    if body:
        task_data["bodyV2"] = {"markdown": body}
    if status:
        task_data["status"] = status
    if dueAt:
        task_data["dueAt"] = dueAt
    resp = _post("tasks", task_data)
    task = resp["data"]["createTask"]
    task_id = task["id"]

    linked = []
    for pid in (personIds or []):
        try:
            _post("taskTargets", {"taskId": task_id, "targetPersonId": pid})
            linked.append(f"person `{pid}`")
        except Exception as e:
            linked.append(f"person `{pid}` (FEIL: {e})")

    for cid in (companyIds or []):
        try:
            _post("taskTargets", {"taskId": task_id, "targetCompanyId": cid})
            linked.append(f"bedrift `{cid}`")
        except Exception as e:
            linked.append(f"bedrift `{cid}` (FEIL: {e})")

    result = f"Oppgave opprettet: **{title}** (id: `{task_id}`, status: {status})"
    if dueAt:
        result += f"\n  Frist: {dueAt}"
    if linked:
        result += f"\nKoblet til: {', '.join(linked)}"
    return result


@mcp.tool()
def list_tasks(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
) -> str:
    """List tasks, optionally filtered by status and/or search text.

    Args:
        status: Filter by status: TODO, IN_PROGRESS, or DONE
        search: Search text to filter tasks
        limit: Max results (default 20)
    """
    if search:
        tasks = _search_objects("tasks", search, limit)
        # Client-side status filter if both are specified
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
    else:
        params: dict = {"limit": str(limit)}
        if status:
            params["filter"] = f"status[eq]:{status}"
        data = _get("tasks", params)
        tasks = data["data"]["tasks"]
    if not tasks:
        return "Ingen oppgaver funnet."
    lines = [f"Fant {len(tasks)} oppgave(r):\n"]
    for t in tasks:
        lines.append(_format_task(t))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_task(id: str) -> str:
    """Get a task with full details and linked targets.

    Args:
        id: Task UUID
    """
    data = _get(f"tasks/{id}")
    t = data["data"]["task"]
    result = _format_task(t)

    targets = _get_targets("taskTargets", "taskId", id)
    if targets:
        result += f"\n\nKoblede mål ({len(targets)} stk): Se task-targets for detaljer."
    return result


@mcp.tool()
def delete_task(id: str) -> str:
    """Delete a task.

    Args:
        id: Task UUID
    """
    data = _delete(f"tasks/{id}")
    return f"Oppgave slettet (id: `{id}`)"


# ---------------------------------------------------------------------------
# Opportunities tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_opportunities(query: str, limit: int = 10) -> str:
    """Search for opportunities by name or other text fields.

    Args:
        query: Search text
        limit: Max results (default 10)
    """
    opps = _search_objects("opportunities", query, limit)
    if not opps:
        return f"Ingen muligheter funnet for '{query}'."
    lines = [f"Fant {len(opps)} mulighet(er) for '{query}':\n"]
    for o in opps:
        lines.append(_format_opportunity(o))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def list_opportunities(stage: Optional[str] = None, limit: int = 20) -> str:
    """List opportunities, optionally filtered by stage.

    Args:
        stage: Filter by stage (e.g. INCOMING, MEETING, PROPOSAL, WON, LOST)
        limit: Max results (default 20)
    """
    params: dict = {"limit": str(limit)}
    if stage:
        params["filter"] = f"stage[eq]:{stage}"
    data = _get("opportunities", params)
    opps = data["data"]["opportunities"]
    if not opps:
        return "Ingen muligheter funnet."
    lines = [f"Fant {len(opps)} mulighet(er):\n"]
    for o in opps:
        lines.append(_format_opportunity(o))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_opportunity(id: str) -> str:
    """Get detailed information about an opportunity.

    Args:
        id: Opportunity UUID
    """
    data = _get(f"opportunities/{id}")
    o = data["data"]["opportunity"]
    return _format_opportunity(o)


@mcp.tool()
def create_opportunity(
    name: str,
    companyId: Optional[str] = None,
    pointOfContactId: Optional[str] = None,
    stage: Optional[str] = None,
    amount: Optional[float] = None,
    currencyCode: Optional[str] = "NOK",
    closeDate: Optional[str] = None,
) -> str:
    """Create a new opportunity in Twenty CRM.

    Args:
        name: Opportunity name
        companyId: Company UUID to link to
        pointOfContactId: Person UUID as point of contact
        stage: Stage (e.g. INCOMING, MEETING, PROPOSAL, WON, LOST)
        amount: Amount in currency units (e.g. 50000 for 50,000 NOK)
        currencyCode: Currency code (default NOK)
        closeDate: Expected close date in ISO 8601 format (e.g. 2026-06-15)
    """
    body: dict = {"name": name}
    if companyId:
        body["companyId"] = companyId
    if pointOfContactId:
        body["pointOfContactId"] = pointOfContactId
    if stage:
        body["stage"] = stage
    if amount is not None:
        body["amount"] = {
            "amountMicros": int(amount * 1_000_000),
            "currencyCode": currencyCode or "NOK",
        }
    if closeDate:
        body["closeDate"] = closeDate
    data = _post("opportunities", body)
    o = data["data"]["createOpportunity"]
    return f"Mulighet opprettet: {_format_opportunity(o)}"


@mcp.tool()
def update_opportunity(
    id: str,
    name: Optional[str] = None,
    stage: Optional[str] = None,
    amount: Optional[float] = None,
    currencyCode: Optional[str] = None,
    closeDate: Optional[str] = None,
    companyId: Optional[str] = None,
    pointOfContactId: Optional[str] = None,
) -> str:
    """Update an existing opportunity.

    Args:
        id: Opportunity UUID
        name: New name
        stage: New stage (e.g. INCOMING, MEETING, PROPOSAL, WON, LOST)
        amount: New amount in currency units
        currencyCode: Currency code (default NOK)
        closeDate: New close date in ISO 8601 format
        companyId: New company UUID
        pointOfContactId: New point of contact person UUID
    """
    body: dict = {}
    if name:
        body["name"] = name
    if stage:
        body["stage"] = stage
    if amount is not None:
        body["amount"] = {
            "amountMicros": int(amount * 1_000_000),
            "currencyCode": currencyCode or "NOK",
        }
    if closeDate:
        body["closeDate"] = closeDate
    if companyId:
        body["companyId"] = companyId
    if pointOfContactId:
        body["pointOfContactId"] = pointOfContactId
    if not body:
        return "Ingen felter å oppdatere."
    data = _patch(f"opportunities/{id}", body)
    o = data["data"]["updateOpportunity"]
    return f"Mulighet oppdatert: {_format_opportunity(o)}"


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_records(query: str, objectTypes: Optional[list[str]] = None) -> str:
    """Search across multiple object types (people, companies, notes, tasks, opportunities).

    Args:
        query: Search text
        objectTypes: Object types to search. Default: people, companies, notes, tasks, opportunities
    """
    types = objectTypes or ["people", "companies", "notes", "tasks", "opportunities"]
    results = []
    for obj_type in types:
        items = _search_objects(obj_type, query, 5)
        if items:
            results.append(f"## {obj_type.capitalize()} ({len(items)} treff)")
            for item in items:
                if obj_type == "people":
                    results.append(_format_person(item))
                elif obj_type == "companies":
                    results.append(_format_company(item))
                elif obj_type == "notes":
                    results.append(_format_note(item))
                elif obj_type == "tasks":
                    results.append(_format_task(item))
                elif obj_type == "opportunities":
                    results.append(_format_opportunity(item))
                results.append("")
    if not results:
        return f"Ingen treff for '{query}'."
    return "\n".join(results)


if __name__ == "__main__":
    mcp.run()
