import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Settings from "./pages/Settings.jsx";
import Skills from "./pages/Skills.jsx";
import NewApplication from "./pages/NewApplication.jsx";
import ApplicationDetail from "./pages/ApplicationDetail.jsx";
import ApplicationsList from "./pages/ApplicationsList.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/applications/new" replace />} />
          <Route path="/applications/new" element={<NewApplication />} />
          <Route path="/applications" element={<ApplicationsList />} />
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
