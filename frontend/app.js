// --- BACKEND URL RESOLUTION ---
const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://127.0.0.1:8000'
    : window.location.origin;

// --- APPLICATION STATE ---
let session = {
    loggedIn: false,
    username: '',
    role: ''
};

// Initial template rows for branch daily operations form
const initialEntries = [
    { particulars: "Opening Balance (A)", category: "Balance", unit: "Rs.", amount: 0.0 },
    { particulars: "Sales Volume (in MT)", category: "Sales", unit: "MT", amount: 0.0 },
    { particulars: "Sales Avg Rate", category: "Sales", unit: "Rs./MT", amount: 0.0 },
    { particulars: "Total Sales in Rs.", category: "Sales", unit: "Rs.", amount: 0.0 },
    { particulars: "Total Expenses", category: "Expenses", unit: "Rs.", amount: 0.0 }
];

let operationsEntries = [];

// Executive portal state cache
let executiveData = {
    entries: [],
    rawEntries: [],
    totals: {}
};
let activeTab = 'consolidated'; // 'consolidated' or 'individual'

// --- DOM ELEMENTS ---
const loginView = document.getElementById('login-view');
const dashboardView = document.getElementById('dashboard-view');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const phoneInput = document.getElementById('phone');
const passwordInput = document.getElementById('password');

// Registration DOM Elements
const registerForm = document.getElementById('register-form');
const regPhoneInput = document.getElementById('reg-phone');
const regPasswordInput = document.getElementById('reg-password');
const regStatus = document.getElementById('reg-status');
const goToRegisterLink = document.getElementById('go-to-register');
const goToLoginLink = document.getElementById('go-to-login');

const sessionDisplay = document.getElementById('session-display');
const logoutBtn = document.getElementById('logout-btn');

const userPortal = document.getElementById('user-portal');
const executivePortal = document.getElementById('executive-portal');

// User Portal Elements
const excelFileInput = document.getElementById('excel-file');
const uploadStatus = document.getElementById('upload-status');
const operationsBody = document.getElementById('operations-body');
const addRowBtn = document.getElementById('add-row-btn');
const syncBtn = document.getElementById('sync-btn');
const syncStatus = document.getElementById('sync-status');

// Executive Portal Elements
const kpiVolume = document.getElementById('kpi-volume');
const kpiSales = document.getElementById('kpi-sales');
const kpiExpenses = document.getElementById('kpi-expenses');
const consolidationBody = document.getElementById('consolidation-body');
const noRecordsMsg = document.getElementById('no-records-msg');
const exportBtn = document.getElementById('export-btn');
const exportStatus = document.getElementById('export-status');

// Sub-navigation DOM Elements
const tabConsolidated = document.getElementById('tab-consolidated');
const tabIndividual = document.getElementById('tab-individual');
const execConsolidatedView = document.getElementById('exec-consolidated-view');
const execIndividualView = document.getElementById('exec-individual-view');

// Individual Filter View DOM Elements
const branchSelector = document.getElementById('branch-selector');
const indKpiVolume = document.getElementById('ind-kpi-volume');
const indKpiSales = document.getElementById('ind-kpi-sales');
const indKpiExpenses = document.getElementById('ind-kpi-expenses');
const individualBody = document.getElementById('individual-body');
const indNoRecordsMsg = document.getElementById('ind-no-records-msg');
const indGridTitle = document.getElementById('ind-grid-title');

// Date selector DOM elements
const userDateFilter = document.getElementById('user-date-filter');
const masterDateFilter = document.getElementById('master-date-filter');


// --- APP INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    // Restore session if available
    const savedSession = sessionStorage.getItem('cash_flow_session');
    if (savedSession) {
        session = JSON.parse(savedSession);
        if (session.loggedIn) {
            showDashboard();
        }
    }
    setupEventListeners();
});

function setupEventListeners() {
    // Authentication & Registration
    loginForm.addEventListener('submit', handleLogin);
    logoutBtn.addEventListener('click', handleLogout);
    goToRegisterLink.addEventListener('click', toggleToRegister);
    goToLoginLink.addEventListener('click', toggleToLogin);
    registerForm.addEventListener('submit', handleRegister);

    // User Operations Form Actions
    excelFileInput.addEventListener('change', handleExcelUpload);
    addRowBtn.addEventListener('click', addNewRow);
    syncBtn.addEventListener('click', syncOperationsData);

    // Executive Actions
    exportBtn.addEventListener('click', exportExcelReport);
    tabConsolidated.addEventListener('click', () => switchTab('consolidated'));
    tabIndividual.addEventListener('click', () => switchTab('individual'));
    branchSelector.addEventListener('change', handleBranchSelect);

    // Date Filters Actions
    userDateFilter.addEventListener('change', handleUserDateChange);
    masterDateFilter.addEventListener('change', handleMasterDateChange);
}

// --- AUTHENTICATION FLOW ---
async function handleLogin(e) {
    e.preventDefault();
    loginError.classList.add('hidden');
    loginError.textContent = '';

    const phone = phoneInput.value.trim();
    const password = passwordInput.value;

    try {
        const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Invalid phone number or password. Try standard credentials.');
        }

        const data = await response.json();
        
        session = {
            loggedIn: true,
            username: data.username,
            role: data.role
        };
        
        sessionStorage.setItem('cash_flow_session', JSON.stringify(session));
        showDashboard();
    } catch (error) {
        loginError.textContent = error.message;
        loginError.classList.remove('hidden');
    }
}

function toggleToRegister(e) {
    e.preventDefault();
    loginForm.classList.add('hidden');
    registerForm.classList.remove('hidden');
    loginError.classList.add('hidden');
    regStatus.classList.add('hidden');
    // Clear inputs
    regPhoneInput.value = '';
    regPasswordInput.value = '';
}

function toggleToLogin(e) {
    if (e) e.preventDefault();
    registerForm.classList.add('hidden');
    loginForm.classList.remove('hidden');
    loginError.classList.add('hidden');
    regStatus.classList.add('hidden');
    // Clear inputs
    phoneInput.value = '';
    passwordInput.value = '';
}

async function handleRegister(e) {
    e.preventDefault();
    regStatus.className = 'status-msg';
    regStatus.classList.add('hidden');
    regStatus.textContent = '';

    const phone = regPhoneInput.value.trim();
    const password = regPasswordInput.value;
    const role = "User Dashboard";

    try {
        const response = await fetch(`${BACKEND_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password, role })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Registration failed.');
        }

        regStatus.textContent = 'Account created successfully! Redirecting to login...';
        regStatus.classList.add('success');
        regStatus.classList.remove('hidden');
        
        // Auto toggle back to login after 2 seconds
        setTimeout(() => {
            toggleToLogin();
            // Autofill the phone number
            phoneInput.value = phone;
        }, 2000);
    } catch (error) {
        regStatus.textContent = error.message;
        regStatus.classList.add('error');
        regStatus.classList.remove('hidden');
    }
}

function handleLogout() {
    session = { loggedIn: false, username: '', role: '' };
    sessionStorage.removeItem('cash_flow_session');
    
    // Clear views
    userPortal.classList.add('hidden');
    executivePortal.classList.add('hidden');
    dashboardView.classList.add('hidden');
    
    // Fix visibility: Remove hidden class
    loginView.classList.remove('hidden');
    loginView.classList.add('view', 'active');
    
    // Clear inputs
    phoneInput.value = '';
    passwordInput.value = '';
    loginError.classList.add('hidden');
}

function showDashboard() {
    loginView.classList.remove('view', 'active');
    loginView.classList.add('hidden');
    dashboardView.classList.remove('hidden');

    sessionDisplay.textContent = `${session.username} (${session.role})`;

    if (session.role === 'User Dashboard') {
        // Load User Form View
        userPortal.classList.remove('hidden');
        executivePortal.classList.add('hidden');
        
        // Default to today if empty
        if (!userDateFilter.value) {
            userDateFilter.value = new Date().toISOString().split('T')[0];
        }
        handleUserDateChange();
    } else {
        // Load Master Executive View
        executivePortal.classList.remove('hidden');
        userPortal.classList.add('hidden');
        loadExecutiveSummary();
    }
}

// --- INTERFACE A: USER PORTAL LOGIC ---

function resetOperationsTable() {
    // Set to deep copy of default entries template
    operationsEntries = JSON.parse(JSON.stringify(initialEntries));
    renderOperationsTable();
}

function renderOperationsTable() {
    operationsBody.innerHTML = '';
    
    operationsEntries.forEach((entry, index) => {
        const tr = document.createElement('tr');
        
        // 1. Particulars (editable text)
        const tdParticulars = document.createElement('td');
        const inputParticulars = document.createElement('input');
        inputParticulars.type = 'text';
        inputParticulars.className = 'table-input';
        inputParticulars.value = entry.particulars;
        inputParticulars.addEventListener('input', (e) => {
            operationsEntries[index].particulars = e.target.value;
        });
        tdParticulars.appendChild(inputParticulars);
        tr.appendChild(tdParticulars);
        
        // 2. Category (editable select)
        const tdCategory = document.createElement('td');
        const selectCategory = document.createElement('select');
        selectCategory.className = 'table-select';
        ['Balance', 'Sales', 'Receipts', 'Expenses'].forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            if (entry.category === cat) opt.selected = true;
            selectCategory.appendChild(opt);
        });
        selectCategory.addEventListener('change', (e) => {
            operationsEntries[index].category = e.target.value;
        });
        tdCategory.appendChild(selectCategory);
        tr.appendChild(tdCategory);
        
        // 3. Unit (editable dropdown select)
        const tdUnit = document.createElement('td');
        const selectUnit = document.createElement('select');
        selectUnit.className = 'table-select';
        ['Rs.', 'MT', 'Rs./MT', 'Nos.', ''].forEach(u => {
            const opt = document.createElement('option');
            opt.value = u;
            opt.textContent = u || 'Select Unit';
            if (entry.unit === u) opt.selected = true;
            selectUnit.appendChild(opt);
        });
        selectUnit.addEventListener('change', (e) => {
            operationsEntries[index].unit = e.target.value;
        });
        tdUnit.appendChild(selectUnit);
        tr.appendChild(tdUnit);
        
        // 3. Amount (editable numeric)
        const tdAmount = document.createElement('td');
        const inputAmount = document.createElement('input');
        inputAmount.type = 'number';
        inputAmount.step = '0.01';
        inputAmount.className = 'table-input';
        inputAmount.value = entry.amount;
        inputAmount.addEventListener('input', (e) => {
            operationsEntries[index].amount = parseFloat(e.target.value) || 0.0;
        });
        tdAmount.appendChild(inputAmount);
        tr.appendChild(tdAmount);
        
        // 4. Action (delete row)
        const tdAction = document.createElement('td');
        tdAction.className = 'actions-col';
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-danger';
        deleteBtn.innerHTML = '✕';
        deleteBtn.addEventListener('click', () => deleteRow(index));
        tdAction.appendChild(deleteBtn);
        tr.appendChild(tdAction);

        operationsBody.appendChild(tr);
    });
}

function addNewRow() {
    operationsEntries.push({
        particulars: '',
        category: 'Balance',
        unit: '',
        amount: 0.0
    });
    renderOperationsTable();
}

function deleteRow(index) {
    operationsEntries.splice(index, 1);
    renderOperationsTable();
}

async function handleExcelUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    uploadStatus.className = 'status-msg';
    uploadStatus.classList.add('hidden');
    uploadStatus.textContent = '';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${BACKEND_URL}/api/user/parse-excel`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed parsing specific excel structure layout.');
        }

        const data = await response.json();
        if (data.entries && data.entries.length > 0) {
            operationsEntries = data.entries;
            if (data.date) {
                userDateFilter.value = data.date;
            }
            renderOperationsTable();
            uploadStatus.textContent = 'Successfully parsed spreadsheet mapping template!';
            uploadStatus.classList.add('success');
            uploadStatus.classList.remove('hidden');
        } else {
            throw new Error('Parsed template returned no data items.');
        }
    } catch (error) {
        uploadStatus.textContent = error.message;
        uploadStatus.classList.add('error');
        uploadStatus.classList.remove('hidden');
    } finally {
        excelFileInput.value = ''; // Reset input element
    }
}

async function syncOperationsData() {
    syncStatus.className = 'status-msg';
    syncStatus.classList.add('hidden');
    syncStatus.textContent = '';

    const payload = {
        username: session.username,
        date: userDateFilter.value,
        entries: operationsEntries
    };

    try {
        const response = await fetch(`${BACKEND_URL}/api/user/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Synchronization failed.');
        }

        syncStatus.textContent = 'Branch reporting synchronization completed successfully!';
        syncStatus.classList.add('success');
        syncStatus.classList.remove('hidden');
    } catch (error) {
        syncStatus.textContent = error.message;
        syncStatus.classList.add('error');
        syncStatus.classList.remove('hidden');
    }
}

// Date change handlers
async function handleUserDateChange() {
    const selectedDate = userDateFilter.value;
    if (!selectedDate) return;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/user/report?username=${session.username}&date=${selectedDate}`);
        if (!response.ok) {
            throw new Error('Failed to fetch user report.');
        }
        const data = await response.json();
        if (data.entries && data.entries.length > 0) {
            operationsEntries = data.entries;
            renderOperationsTable();
        } else {
            // Fresh start for this date
            resetOperationsTable();
        }
    } catch (error) {
        console.error(error);
        resetOperationsTable();
    }
}

function handleMasterDateChange() {
    const selectedDate = masterDateFilter.value;
    if (selectedDate) {
        loadExecutiveSummary(selectedDate);
    }
}

// --- INTERFACE B: EXECUTIVE PORTAL LOGIC ---

// Tab Toggling
function switchTab(tab) {
    activeTab = tab;
    
    // Toggle active classes on tab buttons
    if (tab === 'consolidated') {
        tabConsolidated.classList.add('active');
        tabIndividual.classList.remove('active');
        execConsolidatedView.classList.remove('hidden');
        execIndividualView.classList.add('hidden');
    } else {
        tabIndividual.classList.add('active');
        tabConsolidated.classList.remove('active');
        execIndividualView.classList.remove('hidden');
        execConsolidatedView.classList.add('hidden');
        // Initial render for selected branch
        handleBranchSelect();
    }
}

async function loadExecutiveSummary(targetDate = null) {
    try {
        const url = targetDate 
            ? `${BACKEND_URL}/api/master/summary?date=${targetDate}` 
            : `${BACKEND_URL}/api/master/summary`;
            
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('Failed to query consolidated records.');
        }
        
        const data = await response.json();
        
        // Cache the retrieved data
        executiveData.entries = data.entries || [];
        executiveData.rawEntries = data.raw_entries || [];
        executiveData.totals = data.totals || { volume: 0, sales: 0, expenses: 0 };
        
        // Sync the date filter value in UI
        if (data.date) {
            masterDateFilter.value = data.date;
        }
        
        // 1. Set Consolidated KPIs
        const totals = executiveData.totals;
        kpiVolume.textContent = totals.volume.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        kpiSales.textContent = `₹ ${totals.sales.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        kpiExpenses.textContent = `₹ ${totals.expenses.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        // 2. Set Consolidated Grid (Simplified 2-column)
        renderConsolidationTable(executiveData.entries);
        
        // 3. Populate Branch Dropdown Filter
        populateBranchSelector(executiveData.rawEntries);
        
    } catch (error) {
        console.error(error);
        noRecordsMsg.textContent = 'Could not retrieve master database datasets. Verify Backend API availability.';
        noRecordsMsg.classList.remove('hidden');
    }
}

function renderConsolidationTable(entries) {
    consolidationBody.innerHTML = '';
    
    if (!entries || entries.length === 0) {
        noRecordsMsg.classList.remove('hidden');
        return;
    }
    noRecordsMsg.classList.add('hidden');
    
    // Render body rows (Simplified 2-column: line item particulars, and Consolidated Amount (Rs.))
    entries.forEach(row => {
        const tr = document.createElement('tr');
        
        // Particulars
        const tdPart = document.createElement('td');
        tdPart.textContent = row['particulars'];
        tdPart.style.fontWeight = '500';
        tr.appendChild(tdPart);
        
        // Consolidated Amount (Rs.)
        const tdAmount = document.createElement('td');
        const val = row['Consolidated Amount (Rs.)'];
        tdAmount.textContent = typeof val === 'number' 
            ? val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) 
            : (parseFloat(val) || 0.0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        tr.appendChild(tdAmount);
        
        consolidationBody.appendChild(tr);
    });
}

function populateBranchSelector(rawEntries) {
    branchSelector.innerHTML = '';
    
    // Extract unique branch usernames
    const branches = [...new Set(rawEntries.map(e => e.username))];
    branches.sort();
    
    if (branches.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'No active branches reporting';
        branchSelector.appendChild(opt);
        return;
    }
    
    branches.forEach(b => {
        const opt = document.createElement('option');
        opt.value = b;
        opt.textContent = b;
        branchSelector.appendChild(opt);
    });
}

function handleBranchSelect() {
    const selectedBranch = branchSelector.value;
    individualBody.innerHTML = '';
    
    if (!selectedBranch) {
        indNoRecordsMsg.classList.remove('hidden');
        indGridTitle.textContent = '📋 Branch Operational Report';
        indKpiVolume.textContent = '0.00';
        indKpiSales.textContent = '₹ 0.00';
        indKpiExpenses.textContent = '₹ 0.00';
        return;
    }
    indNoRecordsMsg.classList.add('hidden');
    indGridTitle.textContent = `📋 Operational Report for ${selectedBranch}`;
    
    // Filter raw entries for the selected branch
    const branchRows = executiveData.rawEntries.filter(e => e.username === selectedBranch);
    
    // 1. Calculate specific Branch KPIs
    const branchVolumeRows = branchRows.filter(e => e.particulars.toLowerCase().includes("volume"));
    const branchSalesRows = branchRows.filter(e => e.particulars.toLowerCase().includes("total sales"));
    const branchExpenseRows = branchRows.filter(e => e.particulars.toLowerCase().includes("expenses"));
    
    const bVolume = branchVolumeRows.reduce((sum, e) => sum + e.amount, 0);
    const bSales = branchSalesRows.reduce((sum, e) => sum + e.amount, 0);
    const bExpenses = branchExpenseRows.reduce((sum, e) => sum + e.amount, 0);
    
    indKpiVolume.textContent = bVolume.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    indKpiSales.textContent = `₹ ${bSales.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    indKpiExpenses.textContent = `₹ ${bExpenses.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    
    // 2. Render Branch Rows in table
    branchRows.forEach(row => {
        const tr = document.createElement('tr');
        
        const tdPart = document.createElement('td');
        tdPart.textContent = row.particulars;
        tdPart.style.fontWeight = '500';
        tr.appendChild(tdPart);
        
        const tdCat = document.createElement('td');
        tdCat.textContent = row.category;
        tr.appendChild(tdCat);
        
        const tdUnit = document.createElement('td');
        tdUnit.textContent = row.unit || '';
        tr.appendChild(tdUnit);
        
        const tdAmount = document.createElement('td');
        tdAmount.textContent = row.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        tr.appendChild(tdAmount);
        
        individualBody.appendChild(tr);
    });
}

function exportExcelReport() {
    exportStatus.className = 'status-msg';
    exportStatus.classList.add('hidden');
    exportStatus.textContent = '';

    try {
        const targetDate = masterDateFilter.value || '';
        // Trigger a direct browser file download to the new backend endpoint passing the date
        window.open(`${BACKEND_URL}/api/master/export?date=${targetDate}`, '_blank');
        
        exportStatus.textContent = 'Consolidated report downloaded successfully!';
        exportStatus.classList.add('success');
        exportStatus.classList.remove('hidden');
        setTimeout(() => exportStatus.classList.add('hidden'), 3000);
    } catch (error) {
        exportStatus.textContent = 'Failed to generate report export: ' + error.message;
        exportStatus.classList.add('error');
        exportStatus.classList.remove('hidden');
    }
}
