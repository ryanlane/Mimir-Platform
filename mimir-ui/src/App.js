import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard/Dashboard';
import Scenes from './pages/Scenes/Scenes';
import Channels from './pages/Channels/Channels';
import Display from './pages/Display/Display';
import './App.css';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scenes" element={<Scenes />} />
          <Route path="/channels" element={<Channels />} />
          <Route path="/display" element={<Display />} />
          {/* Catch-all route for unmatched paths */}
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
