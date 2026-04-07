import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin"
             style={{ borderColor: "#6d28d9", borderTopColor: "transparent" }} />
      </div>
    );
  }

  return user ? children : <Navigate to="/login" replace />;
}
