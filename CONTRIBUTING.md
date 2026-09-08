# Contributing to InsureRoute

We are thrilled that you want to contribute to **InsureRoute**! Our goal is to build the world's most resilient and intelligent supply chain risk platform, and community contributions are vital to achieving that.

---

##  How You Can Help
You can contribute in several ways:
- **Code:** Bug fixes, feature additions, performance optimizations.
- **AI/ML:** Improving the Isolation Forest model or enhancing Gemini prompts for better operational advisory.
- **Documentation:** Refining deployment guides, API references, and architecture docs.
- **Design:** Enhancing the React/Tailwind frontend for a better user experience.

---

## ️ Development Setup

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Environment Variables
Copy the template and add your keys:
```bash
cp .env.example .env
```
Required keys:
- `OPENWEATHER_API_KEY`
- `GEMINI_API_KEY`
- `NEWSDATA_API_KEY`

### 2. Backend (FastAPI)
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

---

##  Engineering Standards

To ensure the system remains enterprise-grade, please adhere to the following:

- **Python:** Strict adherence to PEP 8. Use type hints (`typing`) across all new functions.
- **React:** Functional components, hooks (`useEffect`, `useState`, `useQuery`), and modular Tailwind CSS.
- **Architecture:** Maintain strict decoupling between the ML engines, pricing engines, and the API gateway.
- **Commits:** Use conventional commits (e.g., `feat: add dynamic routing`, `fix: resolve NaN in premium calc`).

---

##  Reporting Issues

If you find a bug, please open a GitHub Issue containing:
1. A clear, descriptive title.
2. Steps to reproduce the issue.
3. Expected vs. actual behavior.
4. Environment details (OS, Node version, Python version).

---

## ️ License
By contributing, you agree that your contributions will be licensed under the project's MIT License. Thank you for building the future of InsurTech and logistics with us!