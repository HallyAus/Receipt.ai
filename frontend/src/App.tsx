import { Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Accounts from './pages/Accounts';
import Receipts from './pages/Receipts';

function App() {
  return (
    <div>
      <nav className="nav">
        <div className="container nav-content">
          <NavLink to="/" className="nav-brand">
            Receipt.ai
          </NavLink>
          <div className="nav-links">
            <NavLink
              to="/"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              end
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/accounts"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              Accounts
            </NavLink>
            <NavLink
              to="/receipts"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              Receipts
            </NavLink>
          </div>
        </div>
      </nav>

      <main className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/receipts" element={<Receipts />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
