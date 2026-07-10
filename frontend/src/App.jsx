import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "./components/ProtectedRoute";
import TopNav from "./components/TopNav";
import Home from "./pages/Home";
import Login from "./pages/Login";
import OauthSuccess from "./pages/OauthSuccess";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <>
      <TopNav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/oauth-success" element={<OauthSuccess />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </>
  );
}
