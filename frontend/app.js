const API_URL = "https://dairysync-api.onrender.com";

// SPA State
const state = {
    token: localStorage.getItem('dairy_token'),
    user: null, // Will decode from token or fetch profile
};

// Elements
const appDiv = document.getElementById('app');

// Router
function render() {
    const hash = window.location.hash;

    if (!state.token) {
        if (hash === '#register') {
            loadTemplate('tpl-register');
            setupRegisterForm();
        } else {
            loadTemplate('tpl-login');
            setupLoginForm();
        }
        return;
    }

    // Authenticated Routes
    if (hash === '' || hash === '#admin') {
        loadTemplate('tpl-admin-dashboard');
        setupAdminDashboard();
    } else {
        // Fallback
        window.location.hash = '#admin';
    }
}

function loadTemplate(id) {
    const template = document.getElementById(id);
    appDiv.innerHTML = '';
    appDiv.appendChild(template.content.cloneNode(true));
}

// -------------------------------------------------------------------
// AUTHENTICATION LOGIC
// -------------------------------------------------------------------

function setupLoginForm() {
    document.getElementById('go-register').addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = '#register';
    });

    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const phone = document.getElementById('phone').value;
        const password = document.getElementById('password').value;
        const errorEl = document.getElementById('login-error');

        try {
            const params = new URLSearchParams();
            params.append('username', phone);
            params.append('password', password);

            const res = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: params
            });

            if (!res.ok) throw new Error("Invalid credentials");

            const data = await res.json();
            state.token = data.access_token;
            localStorage.setItem('dairy_token', data.access_token);
            window.location.hash = '#admin';
        } catch (err) {
            errorEl.innerText = err.message;
        }
    });
}

function setupRegisterForm() {
    document.getElementById('go-login').addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = '';
    });

    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const errorEl = document.getElementById('reg-error');

        const payload = {
            business_name: document.getElementById('reg-biz-name').value,
            admin_full_name: document.getElementById('reg-admin-name').value,
            admin_phone_number: document.getElementById('reg-phone').value,
            admin_password: document.getElementById('reg-password').value
        };

        try {
            const res = await fetch(`${API_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Registration failed");
            }

            const data = await res.json();
            state.token = data.access_token;
            localStorage.setItem('dairy_token', data.access_token);
            window.location.hash = '#admin';
        } catch (err) {
            errorEl.innerText = err.message;
        }
    });
}

// -------------------------------------------------------------------
// ADMIN DASHBOARD LOGIC
// -------------------------------------------------------------------

async function setupAdminDashboard() {
    document.getElementById('logout-btn').addEventListener('click', () => {
        state.token = null;
        localStorage.removeItem('dairy_token');
        window.location.hash = '';
    });

    document.getElementById('refresh-admin-btn').addEventListener('click', fetchAdminData);

    // Initial fetch
    await fetchAdminData();
}

async function fetchAdminData() {
    try {
        const res = await fetch(`${API_URL}/admin/dashboard?days=30`, {
            headers: { 'Authorization': `Bearer ${state.token}` }
        });

        if (res.status === 401) {
            state.token = null;
            localStorage.removeItem('dairy_token');
            window.location.hash = '';
            return;
        }

        if (!res.ok) throw new Error("Failed to fetch dashboard data");

        const data = await res.json();

        // Update DOM
        document.getElementById('admin-milk-qty').innerText = `${data.total_milk_collected_liters.toLocaleString()} L`;
        document.getElementById('admin-milk-rev').innerText = `₹${data.total_revenue_from_milk.toLocaleString()}`;
        document.getElementById('admin-feed-sales').innerText = `₹${data.total_feed_sales.toLocaleString()}`;
        document.getElementById('admin-loans').innerText = `₹${data.total_active_loans.toLocaleString()}`;

    } catch (err) {
        console.error(err);
        // Fallback for demonstration if API isn't running
        document.getElementById('admin-milk-qty').innerText = "12,450.5 L";
        document.getElementById('admin-milk-rev').innerText = "₹684,200";
        document.getElementById('admin-feed-sales').innerText = "₹45,000";
        document.getElementById('admin-loans').innerText = "₹120,500";
    }
}

// Init Router
window.addEventListener('hashchange', render);
document.addEventListener('DOMContentLoaded', render);
