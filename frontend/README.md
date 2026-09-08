# InsureRoute Frontend

This is the enterprise-grade React dashboard for **InsureRoute**, serving as the central Operational Command Center for real-time logistics risk monitoring.

---

##  Tech Stack

- **Framework:** React 18
- **Build Tool:** Vite (for ultra-fast HMR and optimized production builds)
- **Styling:** Tailwind CSS (for scalable, utility-first design)
- **State Management & Caching:** React Query
- **Routing:** React Router v6
- **Mapping:** React-Leaflet
- **Icons:** Lucide React

---

##  Architecture & Components

The frontend is fully decoupled from the mathematical processing layer, acting exclusively as a real-time digital twin.

Key components include:
- `InsureRouteDashboard.jsx`: The primary unified operational view.
- `ShipmentSetup.jsx`: The intuitive wizard for defining cargo variables (type, value, priority).
- `KPICards.jsx`: Animated trackers for CO2 offsets, premium arbitrage, and gross cargo value.
- `RouteIntelDrawer.jsx`: The slide-out pane rendering live Gemini AI insights and categorized news streams.

---

## ️ Development Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

---

## ️ Deployment

This frontend is optimized for edge delivery and serverless environments. It can be instantly containerized and deployed to **Google Cloud Run** or pushed globally via **Firebase Hosting**.

For detailed deployment steps, refer to the root `deployment_guide.md`.