import os
import requests
import pandas as pd
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = "http://localhost:8000"
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")

PIN_COLORS = {
    "Hot Lead":   "red",
    "Warm Lead":  "orange",
    "Not a Lead": "green",
}

# Friendly label → Google Places API (New) type string
BUSINESS_TYPES = {
    "Restaurant": "restaurant",
    "Cafe": "cafe",
    "Bakery": "bakery",
    "Bar": "bar",
    "Hair Salon": "hair_salon",
    "Beauty Salon": "beauty_salon",
    "Spa": "spa",
    "Gym": "gym",
    "Auto Repair": "car_repair",
    "Plumber": "plumber",
    "Electrician": "electrician",
    "Dentist": "dentist",
    "Doctor": "doctor",
    "Veterinary Care": "veterinary_care",
    "Real Estate Agency": "real_estate_agency",
    "Lawyer": "lawyer",
    "Accounting": "accounting",
    "Clothing Store": "clothing_store",
    "Furniture Store": "furniture_store",
    "Florist": "florist",
    "Pet Store": "pet_store",
    "Hardware Store": "hardware_store",
    "Book Store": "book_store",
    "Jewelry Store": "jewelry_store",
}

st.set_page_config(page_title="Small Business Scanner", layout="wide")
st.title("Small Business Scanner")

# Session state defaults
for key, default in [("businesses", []), ("drawn_geometry", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Scan Settings")
    max_res = st.slider("Max results", 5, 20, 20)
    selected_type_labels = st.multiselect(
        "Business types",
        list(BUSINESS_TYPES.keys()),
        help="Leave empty to search all business types.",
    )
    included_types = [BUSINESS_TYPES[label] for label in selected_type_labels]
    st.divider()
    st.header("Filter")
    status_filter = st.selectbox(
        "Lead Status",
        ["All", "Hot Lead", "Warm Lead", "Not a Lead"],
    )

# ── Load existing businesses on first run ─────────────────────────────────────
if not st.session_state["businesses"]:
    try:
        resp = requests.get(f"{API_BASE}/businesses", timeout=15)
        resp.raise_for_status()
        st.session_state["businesses"] = resp.json()
    except Exception:
        pass

businesses = st.session_state["businesses"]

# ── Map ───────────────────────────────────────────────────────────────────────
st.subheader("Select Search Area")
st.caption("Draw a **circle** (pin + drag to set radius) or a **rectangle** on the map, then click **Scan This Area**.")

if businesses:
    lats = [b.get("Lat", 0) for b in businesses if b.get("Lat")]
    lngs = [b.get("Lng", 0) for b in businesses if b.get("Lng")]
    map_center = [sum(lats) / len(lats), sum(lngs) / len(lngs)] if lats else [39.5, -98.35]
    map_zoom = 12
else:
    map_center = [39.5, -98.35]
    map_zoom = 4

m = folium.Map(location=map_center, zoom_start=map_zoom, tiles=None)

if MAPBOX_TOKEN:
    folium.TileLayer(
        tiles=(
            f"https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/256/{{z}}/{{x}}/{{y}}"
            f"?access_token={MAPBOX_TOKEN}"
        ),
        attr="© <a href='https://www.mapbox.com/about/maps/'>Mapbox</a> © <a href='http://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
        name="Mapbox Streets",
        max_zoom=20,
    ).add_to(m)
else:
    folium.TileLayer("OpenStreetMap").add_to(m)

Draw(
    draw_options={
        "polyline": False,
        "polygon": False,
        "circle": True,
        "marker": False,
        "circlemarker": False,
        "rectangle": True,
    },
    edit_options={"edit": False, "remove": True},
).add_to(m)

# Render existing business markers
filtered = [b for b in businesses if status_filter == "All" or b.get("Lead Status") == status_filter]
for biz in filtered:
    lat = biz.get("Lat") or biz.get("lat")
    lng = biz.get("Lng") or biz.get("lng")
    if not lat or not lng:
        continue
    status = biz.get("Lead Status") or biz.get("lead_status", "")
    color = PIN_COLORS.get(status, "gray")
    name = biz.get("Name") or biz.get("name", "")
    addr = biz.get("Address") or biz.get("address", "")
    folium.CircleMarker(
        location=[lat, lng],
        radius=9,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        popup=folium.Popup(f"<b>{name}</b><br>{status}<br>{addr}", max_width=220),
    ).add_to(m)

map_output = st_folium(m, use_container_width=True, height=560, key="main_map")

# Capture the drawn shape into session state
if map_output and map_output.get("last_active_drawing"):
    st.session_state["drawn_geometry"] = map_output["last_active_drawing"]

# ── Scan controls ─────────────────────────────────────────────────────────────
geom = st.session_state.get("drawn_geometry")

if geom:
    g_type = geom.get("geometry", {}).get("type")

    if g_type == "Point":
        coords = geom["geometry"]["coordinates"]
        center_lng, center_lat = coords[0], coords[1]
        radius_m = geom.get("properties", {}).get("radius", 1000)
        radius_miles = radius_m / 1609.34
        st.info(
            f"Circle — center ({center_lat:.5f}, {center_lng:.5f}), "
            f"radius {radius_miles:.2f} mi ({radius_m:.0f} m)"
        )
        scan_payload = {
            "lat": center_lat,
            "lng": center_lng,
            "radius_miles": radius_miles,
            "max_results": max_res,
            "included_types": included_types,
        }

    elif g_type == "Polygon":
        coords = geom["geometry"]["coordinates"][0]
        lngs_list = [c[0] for c in coords]
        lats_list = [c[1] for c in coords]
        bounds = {
            "min_lat": min(lats_list), "max_lat": max(lats_list),
            "min_lng": min(lngs_list), "max_lng": max(lngs_list),
        }
        st.info(
            f"Rectangle — lat [{bounds['min_lat']:.5f} → {bounds['max_lat']:.5f}], "
            f"lng [{bounds['min_lng']:.5f} → {bounds['max_lng']:.5f}]"
        )
        scan_payload = {"bounds": bounds, "max_results": max_res, "included_types": included_types}

    else:
        scan_payload = None

    if scan_payload and st.button("Scan This Area", type="primary"):
        with st.spinner("Scanning..."):
            try:
                resp = requests.post(f"{API_BASE}/scan", json=scan_payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                normalized = []
                for b in data.get("businesses", []):
                    normalized.append({
                        "id": b.get("id", ""),
                        "Name": b.get("name", ""),
                        "Address": b.get("address", ""),
                        "Phone": b.get("phone", ""),
                        "Website URL": b.get("website_url", ""),
                        "Category": b.get("category", ""),
                        "Rating": b.get("rating", 0),
                        "Review Count": b.get("review_count", 0),
                        "Lead Status": b.get("lead_status", ""),
                        "Lat": b.get("lat", 0),
                        "Lng": b.get("lng", 0),
                    })
                st.session_state["businesses"] = normalized
                st.success(f"Found {data['total']} businesses.")
                st.rerun()
            except Exception as e:
                st.error(f"Scan failed: {e}")
else:
    st.info("Draw a circle or rectangle on the map above to define your search area.")

# ── Results ───────────────────────────────────────────────────────────────────
if businesses:
    df = pd.DataFrame(businesses)
    if status_filter != "All" and "Lead Status" in df.columns:
        df = df[df["Lead Status"] == status_filter]

    col1, col2, col3 = st.columns(3)
    all_df = pd.DataFrame(businesses)
    ls = all_df["Lead Status"] if "Lead Status" in all_df.columns else pd.Series(dtype=str)
    col1.metric("Hot Leads",  int((ls == "Hot Lead").sum()))
    col2.metric("Warm Leads", int((ls == "Warm Lead").sum()))
    col3.metric("Not a Lead", int((ls == "Not a Lead").sum()))

    st.divider()
    st.subheader("Businesses")
    display_cols = ["Name", "Lead Status", "Category", "Rating", "Review Count", "Address", "Website URL"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)

    # ── Proposal generator ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Generate Website Proposal")

    leads_df = df[df["Lead Status"].isin(["Hot Lead", "Warm Lead"])] if "Lead Status" in df.columns else pd.DataFrame()
    if leads_df.empty:
        st.info("No hot or warm leads in current view.")
    else:
        options = {row["Name"]: row["id"] for _, row in leads_df.iterrows() if row.get("id")}
        if options:
            selected_name = st.selectbox("Select a business", list(options.keys()))
            selected_id = options[selected_name]

            if st.button("Generate Proposal", type="primary"):
                with st.spinner("Claude is writing the proposal..."):
                    try:
                        resp = requests.post(f"{API_BASE}/propose/{selected_id}", timeout=60)
                        resp.raise_for_status()
                        p = resp.json()

                        st.success("Proposal ready!")
                        st.markdown(f"### {p.get('headline', '')}")
                        st.markdown(f"*{p.get('tagline', '')}*")
                        st.divider()

                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("**Design Brief**")
                            st.write(p.get("design_brief", ""))
                            st.markdown("**Suggested Sections**")
                            for s in p.get("sections", []):
                                st.markdown(f"- {s}")
                        with col_b:
                            st.markdown("**Key Selling Points**")
                            for sp in p.get("selling_points", []):
                                st.markdown(f"- {sp}")
                            st.markdown("**SEO Keywords**")
                            st.write(", ".join(p.get("seo_keywords", [])))

                    except Exception as e:
                        st.error(f"Proposal failed: {e}")
