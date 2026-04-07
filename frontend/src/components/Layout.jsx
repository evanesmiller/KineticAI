import Navbar from "./Navbar";

export default function Layout({ children }) {
  return (
    <div style={{ minHeight: "100vh", background: "#080810" }}>
      <Navbar />
      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {children}
      </main>
    </div>
  );
}
