import axios from 'axios';

const DEFAULT_BACKEND_URL =
  window.location.hostname === 'localhost' && window.location.port === '3000'
    ? 'http://localhost:8001'
    : window.location.origin;

export const BACKEND_URL = (
  process.env.REACT_APP_API_URL ||
  process.env.REACT_APP_BACKEND_URL ||
  DEFAULT_BACKEND_URL
).replace(/\/$/, '');

export const API = `${BACKEND_URL}/api`;

axios.defaults.withCredentials = true;
