"""
Built-in list of Indian cities/towns. Used for:
  * instant A-Z autocomplete from the very first keystroke (no API call)
  * finding place names inside chat questions without needing an LLM
  * the India-wide alert scan and map markers (rows flagged "S")
Flags: C = coastal (marine data makes sense), H = hill station / high altitude,
       S = major city included in the India-wide scan + map.
"""
import math

# name | state | lat | lon | flags
_RAW = """
Agartala|Tripura|23.83|91.28|S
Agra|Uttar Pradesh|27.18|78.02|
Ahmedabad|Gujarat|23.03|72.58|S
Aizawl|Mizoram|23.73|92.72|H
Ajmer|Rajasthan|26.45|74.64|
Alappuzha|Kerala|9.49|76.34|C
Amritsar|Punjab|31.63|74.87|S
Anantapur|Andhra Pradesh|14.68|77.60|
Aurangabad|Maharashtra|19.88|75.34|
Ballari|Karnataka|15.14|76.92|
Belagavi|Karnataka|15.85|74.50|
Bengaluru|Karnataka|12.97|77.59|S
Berhampur|Odisha|19.31|84.79|C
Bhavnagar|Gujarat|21.76|72.15|C
Bhopal|Madhya Pradesh|23.26|77.41|S
Bhubaneswar|Odisha|20.30|85.82|S
Bhuj|Gujarat|23.25|69.67|
Bikaner|Rajasthan|28.02|73.31|
Chandigarh|Chandigarh|30.73|76.78|S
Chengalpattu|Tamil Nadu|12.69|79.98|
Chennai|Tamil Nadu|13.08|80.27|CS
Coimbatore|Tamil Nadu|11.02|76.96|
Cuttack|Odisha|20.46|85.88|
Darjeeling|West Bengal|27.04|88.26|H
Davangere|Karnataka|14.47|75.92|
Dehradun|Uttarakhand|30.32|78.03|S
Delhi|Delhi|28.61|77.21|S
Dhanbad|Jharkhand|23.80|86.43|
Dibrugarh|Assam|27.48|94.91|
Durgapur|West Bengal|23.55|87.32|
Erode|Tamil Nadu|11.34|77.72|
Faridabad|Haryana|28.41|77.31|
Gangtok|Sikkim|27.33|88.61|HS
Gaya|Bihar|24.80|85.00|
Ghaziabad|Uttar Pradesh|28.67|77.45|
Goa (Panaji)|Goa|15.49|73.83|CS
Gorakhpur|Uttar Pradesh|26.76|83.37|
Guntur|Andhra Pradesh|16.31|80.44|
Gurugram|Haryana|28.46|77.03|
Guwahati|Assam|26.14|91.74|S
Gwalior|Madhya Pradesh|26.22|78.18|
Haridwar|Uttarakhand|29.95|78.16|
Hosur|Tamil Nadu|12.74|77.83|
Hubballi|Karnataka|15.36|75.12|
Hyderabad|Telangana|17.39|78.49|S
Imphal|Manipur|24.82|93.94|S
Indore|Madhya Pradesh|22.72|75.86|S
Itanagar|Arunachal Pradesh|27.09|93.62|H
Jabalpur|Madhya Pradesh|23.18|79.99|
Jaipur|Rajasthan|26.91|75.79|S
Jaisalmer|Rajasthan|26.92|70.91|
Jalandhar|Punjab|31.33|75.58|
Jammu|Jammu and Kashmir|32.73|74.87|S
Jamnagar|Gujarat|22.47|70.07|C
Jamshedpur|Jharkhand|22.80|86.20|
Jhansi|Uttar Pradesh|25.45|78.57|
Jodhpur|Rajasthan|26.24|73.02|
Kalaburagi|Karnataka|17.33|76.83|
Kancheepuram|Tamil Nadu|12.83|79.70|
Kanpur|Uttar Pradesh|26.45|80.35|
Kanyakumari|Tamil Nadu|8.09|77.54|C
Kannur|Kerala|11.87|75.37|C
Kargil|Ladakh|34.56|76.13|H
Kochi|Kerala|9.93|76.27|CS
Kodaikanal|Tamil Nadu|10.24|77.49|H
Kohima|Nagaland|25.67|94.11|H
Kolhapur|Maharashtra|16.70|74.24|
Kolkata|West Bengal|22.57|88.36|CS
Kota|Rajasthan|25.21|75.86|
Kozhikode|Kerala|11.26|75.78|C
Kurnool|Andhra Pradesh|15.83|78.04|
Kavaratti|Lakshadweep|10.57|72.64|CS
Leh|Ladakh|34.15|77.58|HS
Lucknow|Uttar Pradesh|26.85|80.95|S
Ludhiana|Punjab|30.90|75.86|
Madurai|Tamil Nadu|9.93|78.12|
Manali|Himachal Pradesh|32.24|77.19|H
Mandya|Karnataka|12.52|76.90|
Mangaluru|Karnataka|12.91|74.86|CS
Meerut|Uttar Pradesh|28.98|77.71|
Mount Abu|Rajasthan|24.59|72.71|H
Mumbai|Maharashtra|19.08|72.88|CS
Muzaffarpur|Bihar|26.12|85.39|
Mysuru|Karnataka|12.30|76.64|
Nagpur|Maharashtra|21.15|79.09|S
Nainital|Uttarakhand|29.39|79.46|H
Nashik|Maharashtra|19.99|73.79|
Nellore|Andhra Pradesh|14.44|79.99|C
Noida|Uttar Pradesh|28.54|77.39|
Ooty|Tamil Nadu|11.41|76.69|H
Patna|Bihar|25.59|85.14|S
Port Blair|Andaman and Nicobar|11.62|92.73|CS
Puducherry|Puducherry|11.94|79.81|C
Pune|Maharashtra|18.52|73.86|S
Puri|Odisha|19.81|85.83|C
Raipur|Chhattisgarh|21.25|81.63|S
Rajkot|Gujarat|22.30|70.80|
Rameswaram|Tamil Nadu|9.29|79.31|C
Ranchi|Jharkhand|23.34|85.31|S
Rishikesh|Uttarakhand|30.09|78.27|
Rourkela|Odisha|22.26|84.85|
Salem|Tamil Nadu|11.66|78.15|
Sambalpur|Odisha|21.47|83.97|
Shillong|Meghalaya|25.58|91.89|HS
Shimla|Himachal Pradesh|31.10|77.17|HS
Shivamogga (Shimoga)|Karnataka|13.93|75.57|
Siliguri|West Bengal|26.73|88.40|
Srinagar|Jammu and Kashmir|34.08|74.80|HS
Surat|Gujarat|21.17|72.83|CS
Thane|Maharashtra|19.22|72.98|C
Thanjavur|Tamil Nadu|10.79|79.14|
Thiruvananthapuram|Kerala|8.52|76.94|CS
Thoothukudi|Tamil Nadu|8.76|78.13|C
Thrissur|Kerala|10.53|76.21|
Tiruchirappalli|Tamil Nadu|10.79|78.69|
Tirunelveli|Tamil Nadu|8.73|77.70|
Tirupati|Andhra Pradesh|13.63|79.42|
Tumakuru|Karnataka|13.34|77.10|
Udaipur|Rajasthan|24.59|73.71|
Udupi|Karnataka|13.34|74.75|C
Ujjain|Madhya Pradesh|23.18|75.78|
Vadodara|Gujarat|22.31|73.18|
Varanasi|Uttar Pradesh|25.32|83.01|S
Vellore|Tamil Nadu|12.92|79.13|
Vijayawada|Andhra Pradesh|16.51|80.65|
Visakhapatnam|Andhra Pradesh|17.69|83.22|CS
Warangal|Telangana|17.97|79.60|
"""

CITIES = []
for line in _RAW.strip().splitlines():
    name, state, lat, lon, flags = line.split("|")
    CITIES.append({
        "name": name, "state": state, "lat": float(lat), "lon": float(lon),
        "coastal": "C" in flags, "hill": "H" in flags, "scan": "S" in flags,
    })
CITIES.sort(key=lambda c: c["name"].lower())

SCAN_CITIES = [c for c in CITIES if c["scan"]]
STATES = sorted({c["state"] for c in CITIES})


def _aliases(c):
    """Names a user might type for this city (e.g. 'Panaji' for 'Goa (Panaji)')."""
    n = c["name"]
    out = {n.lower()}
    if "(" in n:
        base, alt = n.split("(")
        out.add(base.strip().lower())
        out.add(alt.strip(") ").lower())
    return out


ALIASES = {}
for _c in CITIES:
    for _a in _aliases(_c):
        ALIASES[_a] = _c
ALIASES.update({
    "bangalore": ALIASES["bengaluru"], "bombay": ALIASES["mumbai"],
    "madras": ALIASES["chennai"], "calcutta": ALIASES["kolkata"],
    "trivandrum": ALIASES["thiruvananthapuram"], "cochin": ALIASES["kochi"],
    "vizag": ALIASES["visakhapatnam"], "mysore": ALIASES["mysuru"],
    "mangalore": ALIASES["mangaluru"], "pondicherry": ALIASES["puducherry"],
    "new delhi": ALIASES["delhi"], "gurgaon": ALIASES["gurugram"],
    "trichy": ALIASES["tiruchirappalli"], "shimoga": ALIASES["shivamogga (shimoga)"],
    "goa": ALIASES["goa (panaji)"], "panaji": ALIASES["goa (panaji)"],
    "ooty": ALIASES["ooty"], "kancheepuram": ALIASES["kancheepuram"],
    "kanchipuram": ALIASES["kancheepuram"], "prayagraj": ALIASES["varanasi"],
})
ALIASES.pop("prayagraj", None)  # don't silently map Prayagraj to Varanasi


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def prefix_search(q: str, limit: int = 10):
    """A-Z suggestions: names that START with the typed letters come first,
    then names that merely contain them. Each group is alphabetical."""
    q = q.strip().lower()
    if not q:
        return [c for c in CITIES if c["scan"]][:limit]
    starts, contains = [], []
    for c in CITIES:
        names = _aliases(c)
        if any(n.startswith(q) for n in names):
            starts.append(c)
        elif any(q in n for n in names):
            contains.append(c)
    return (starts + contains)[:limit]


def nearest(lat, lon, max_km=60):
    best, best_d = None, 1e9
    for c in CITIES:
        d = haversine_km(lat, lon, c["lat"], c["lon"])
        if d < best_d:
            best, best_d = c, d
    return (best, best_d) if best and best_d <= max_km else (None, best_d)


def find_in_text(text: str):
    """Find known city names inside a sentence, in order of appearance."""
    import re
    low = " " + re.sub(r"[^a-z0-9\s\(\)]", " ", text.lower()) + " "
    hits = []
    for alias in sorted(ALIASES, key=len, reverse=True):
        for m in re.finditer(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low):
            hits.append((m.start(), m.end(), ALIASES[alias]))
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out, last_end = [], -1
    for s, e, c in hits:
        if s >= last_end:
            if not out or out[-1]["name"] != c["name"]:
                out.append(c)
            last_end = e
    return out
