import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.scanner import search_businesses, geocode_location, haversine_miles
from backend.analyzer import analyze_website
from backend.proposal import generate_proposal
from backend.database import scans_table, businesses_table, proposals_table

load_dotenv()

app = FastAPI(title="Small Business Scanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BoundsModel(BaseModel):
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


class ScanRequest(BaseModel):
    location: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_miles: float = 5.0
    max_results: int = 20
    bounds: BoundsModel | None = None
    included_types: list[str] | None = None


@app.post("/scan")
def run_scan(req: ScanRequest):
    if req.bounds:
        b = req.bounds
        lat = (b.min_lat + b.max_lat) / 2
        lng = (b.min_lng + b.max_lng) / 2
        radius_miles = max(
            haversine_miles(lat, lng, b.min_lat, b.min_lng),
            haversine_miles(lat, lng, b.max_lat, b.max_lng),
        )
        businesses = search_businesses(lat, lng, radius_miles, req.max_results, req.included_types)
        businesses = [
            biz for biz in businesses
            if b.min_lat <= biz["lat"] <= b.max_lat and b.min_lng <= biz["lng"] <= b.max_lng
        ]
        location_query = f"Rectangle ({lat:.4f}, {lng:.4f})"
    elif req.lat is not None and req.lng is not None:
        lat, lng = req.lat, req.lng
        radius_miles = req.radius_miles
        businesses = search_businesses(lat, lng, radius_miles, req.max_results, req.included_types)
        location_query = f"Pin ({lat:.4f}, {lng:.4f})"
    elif req.location:
        lat, lng = geocode_location(req.location)
        radius_miles = req.radius_miles
        businesses = search_businesses(lat, lng, radius_miles, req.max_results, req.included_types)
        location_query = req.location
    else:
        raise HTTPException(status_code=400, detail="Provide location, lat/lng, or bounds")

    scan_record = scans_table().create({
        "Location Query": location_query,
        "Lat": lat,
        "Lng": lng,
        "Radius Miles": radius_miles,
        "Total Results": len(businesses),
        "Created At": datetime.utcnow().isoformat(),
    })
    scan_id = scan_record["id"]

    saved_businesses = []
    for biz in businesses:
        score = analyze_website(biz.get("website_url", ""))
        record = businesses_table().create({
            "Name": biz["name"],
            "Address": biz["address"],
            "Phone": biz["phone"],
            "Website URL": biz.get("website_url", ""),
            "Category": biz["category"],
            "Rating": biz["rating"],
            "Review Count": biz["review_count"],
            "Lead Status": score["lead_status"],
            "Website Signals": ", ".join(score.get("signals", [])),
            "Lat": biz["lat"],
            "Lng": biz["lng"],
            "Scan ID": scan_id,
        })
        saved_businesses.append({
            **biz,
            "id": record["id"],
            "lead_status": score["lead_status"],
            "reason": score["reason"],
            "signals": score.get("signals", []),
        })

    return {"scan_id": scan_id, "total": len(saved_businesses), "businesses": saved_businesses}


@app.post("/propose/{business_id}")
def propose(business_id: str):
    records = businesses_table().all(formula=f"RECORD_ID()='{business_id}'")
    if not records:
        raise HTTPException(status_code=404, detail="Business not found")

    fields = records[0]["fields"]
    business = {
        "name": fields.get("Name", ""),
        "category": fields.get("Category", ""),
        "address": fields.get("Address", ""),
        "phone": fields.get("Phone", ""),
        "rating": fields.get("Rating", 0),
        "review_count": fields.get("Review Count", 0),
        "website_url": fields.get("Website URL", ""),
        "reviews": [],
    }

    proposal = generate_proposal(business)

    record = proposals_table().create({
        "Business Name": business["name"],
        "Design Brief": proposal.get("design_brief", ""),
        "Sections": ", ".join(proposal.get("sections", [])),
        "Headline": proposal.get("headline", ""),
        "Tagline": proposal.get("tagline", ""),
        "Selling Points": "\n".join(proposal.get("selling_points", [])),
        "SEO Keywords": ", ".join(proposal.get("seo_keywords", [])),
        "Business ID": business_id,
        "Created At": datetime.utcnow().isoformat(),
    })

    return {"proposal_id": record["id"], **proposal}


@app.get("/businesses")
def list_businesses(scan_id: str | None = None, lead_status: str | None = None):
    formula_parts = []
    if scan_id:
        formula_parts.append(f"{{Scan ID}}='{scan_id}'")
    if lead_status:
        formula_parts.append(f"{{Lead Status}}='{lead_status}'")

    formula = f"AND({','.join(formula_parts)})" if formula_parts else None
    records = businesses_table().all(formula=formula)
    return [{"id": r["id"], **r["fields"]} for r in records]


@app.get("/scans")
def list_scans():
    records = scans_table().all(sort=["-Created At"])
    return [{"id": r["id"], **r["fields"]} for r in records]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    return {"mapbox_token": os.getenv("MAPBOX_TOKEN", "")}


# Serve the frontend — must be LAST so API routes take precedence
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/")
def serve_root():
    return FileResponse(str(_frontend_dir / "index.html"))

if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=False), name="static")
