import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import AuthPage    from "./pages/AuthPage";
import Dashboard   from "./pages/Dashboard";
import LogWorkout  from "./pages/LogWorkout";
import History     from "./pages/History";
import Evaluation  from "./pages/Evaluation";
import Profile     from "./pages/Profile";

const Guard = ({ children }) => <ProtectedRoute>{children}</ProtectedRoute>;

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login"      element={<AuthPage />} />
          <Route path="/register"   element={<AuthPage />} />
          <Route path="/dashboard"  element={<Guard><Dashboard /></Guard>} />
          <Route path="/log"        element={<Guard><LogWorkout /></Guard>} />
          <Route path="/history"    element={<Guard><History /></Guard>} />
          <Route path="/evaluation" element={<Guard><Evaluation /></Guard>} />
          <Route path="/profile"    element={<Guard><Profile /></Guard>} />
          <Route path="*"           element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
