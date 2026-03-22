const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const apiClient = {
  async login(username, password) {
    const response = await fetch(`${API_URL}/api/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    return response.json();
  },

  async register(username, password) {
    const response = await fetch(`${API_URL}/api/register`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    return response.json();
  },

  async getConfig() {
    const response = await fetch(`${API_URL}/api/config`, {
      credentials: 'include'
    });
    return response.json();
  },

  async scrape(config) {
    const response = await fetch(`${API_URL}/api/scrape`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    return response.json();
  },

  async getLatestData() {
    const response = await fetch(`${API_URL}/api/latest-data`, {
      credentials: 'include'
    });
    return response.json();
  },

  async calculate(data) {
    const response = await fetch(`${API_URL}/api/calculate`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  },

  async logout() {
    const response = await fetch(`${API_URL}/api/logout`, {
      method: 'POST',
      credentials: 'include'
    });
    return response.json();
  }
};

export default apiClient;
