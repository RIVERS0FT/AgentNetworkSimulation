# Campus Atlas Design System (WebStyle)

Version: 1.0

---

## Design Goal

Create a premium architectural masterplan atlas. The result should look like a campus planning blueprint, architectural site plan, printed planning atlas, or GIS planning document.

**NOT:** dashboard, military map, digital twin cockpit, monitoring platform, cyberpunk interface.

---

## Visual Personality

Calm · Professional · Architectural · Cartographic · Printed · Premium · Minimal

---

## Color System

### Paper
- Background: `#ECE8DF`
- Primary Canvas: `#F7F4EE`

### Buildings
- Fill: `#D4CCBC`
- Stroke: `#8B8475`

### Roads
- `#A89F90` — no black roads.

### Water
- `#AFC6D9` — no bright blue, no gradients.

### Green
- `#9CAF88`

### Text
- Primary: `#2A2A2A`
- Secondary: `#6A665F`

### Accent (Huawei Red)
- `#CF0A2C` — use only for headquarters, important landmarks, selected object.
- Never use glow effects.

---

## Typography

Fonts: **Inter**, **IBM Plex Sans**, **DIN**.  
All labels: **UPPERCASE**. Tracking: `0.08em`. Weight: `500`.

---

## Shadows

Very subtle. Allowed: `0 1px 2px rgba(0,0,0,0.08)`.  
**Forbidden:** Glow, Neon, Outer Shadow, Bloom.

---

## Buildings

Buildings are architectural footprints, not icons.  
Forms: rectangle, courtyard, cluster, campus complex.  
No rounded cards. No UI widgets.

---

## Roads

Site plan roads. Stroke: 1–2px. Color: `#A89F90`. No black roads.

---

## Water

Smooth organic geometry. No bright blue. No gradients.

---

## Green Areas

Large continuous zones. Avoid isolated blobs.  
Create: central park, ecological corridor, lake belt, landscape buffer.

---

## Labels

### District Labels
Large, low opacity (0.10–0.15). UPPERCASE.  
Examples: `RESEARCH DISTRICT`, `AI CAMPUS`, `INNOVATION HUB`, `DATA CENTER ZONE`.

### Landmark Labels
Architectural callout style — black border, white background, **no rounded corners**.

---

## Connections

Connections must be roads, walkways, or greenways.  
**No** UML-style links. **No** relationship graph curves.

---

## Grid (Optional)

If enabled: opacity < 5%, nearly invisible.

---

## Icons

Flat monochrome only: Building, Park, Water, Parking, Transit.  
**No** colorful circles. **No** glowing nodes.

---

## Information Density

70% map · 20% labels · 10% metadata

---

## Metadata

Top header: `CAMPUS ATLAS`, `Huawei Smart Campus Masterplan`, Date, Seed, Scale.  
Bottom right: Scale Bar, North Arrow, Map Reference. **Only.**

---

## Forbidden Elements

❌ Glow Effects ❌ Neon Colors ❌ Floating Widgets ❌ Cyberpunk UI  
❌ Bright Green Dots ❌ Blue Circle Markers ❌ Relationship Graph Curves  
❌ Dashboard Panels ❌ Monitoring Charts ❌ Military Symbols ❌ Tactical Arrows  
❌ Large Black Ellipses ❌ Random Connector Lines

---

## Desired Impression

> "This looks like a real architectural planning atlas for a Huawei research campus."

Not: "This is a dashboard." Not: "This is a game map." Not: "This is a military map."
