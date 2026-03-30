const API_URL = "http://127.0.0.1:8000";
let completedCourses = [];
let sourceDataRaw = []; // Store raw chunks for current generated response

// DOM Elements
const chatWindow = document.getElementById("chat-window");
const questionInput = document.getElementById("question-input");
const btnAsk = document.getElementById("btn-ask");
const courseInput = document.getElementById("course-input");
const btnAddCourse = document.getElementById("add-course-btn");
const courseList = document.getElementById("course-list");
const maxCoursesInput = document.getElementById("max-courses");
const btnPlan = document.getElementById("btn-plan");
const statusDot = document.querySelector(".status-dot");
const modal = document.getElementById("source-modal");
const closeModalBtn = document.querySelector(".close-modal");
const modalBody = document.getElementById("modal-body");

// Initial state checks
checkConnection();

// --- Event Listeners ---
btnAsk.addEventListener("click", handleAsk);
questionInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleAsk();
});

btnAddCourse.addEventListener("click", addCourse);
courseInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") addCourse();
});

btnPlan.addEventListener("click", handlePlan);

// Modal listeners
closeModalBtn.addEventListener("click", () => modal.style.display = "none");
window.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
});

// --- Functionality ---

async function checkConnection() {
    try {
        const res = await fetch(`${API_URL}/health`);
        if (res.ok) {
            statusDot.classList.add("online");
            statusDot.style.background = "var(--accent)";
            statusDot.style.boxShadow = "0 0 10px var(--accent)";
        }
    } catch (e) {
        statusDot.style.background = "var(--danger)";
        statusDot.style.boxShadow = "0 0 10px var(--danger)";
        appendMessage("System", "Could not connect to the backend server. Is it running on port 8000?", "system-message");
    }
}

function addCourse() {
    const val = courseInput.value.trim().toUpperCase();
    if (val && !completedCourses.includes(val)) {
        completedCourses.push(val);
        renderCourses();
        courseInput.value = "";
    }
}

function removeCourse(course) {
    completedCourses = completedCourses.filter(c => c !== course);
    renderCourses();
}

function renderCourses() {
    courseList.innerHTML = "";
    completedCourses.forEach(course => {
        const chip = document.createElement("div");
        chip.className = "course-chip";
        chip.innerHTML = `
            ${course}
            <button onclick="removeCourse('${course}')">&times;</button>
        `;
        courseList.appendChild(chip);
    });
}

function showTypingIndicator() {
    const loader = document.createElement("div");
    loader.className = "message system-message typing-indicator-msg";
    loader.innerHTML = `
        <div class="avatar">🤖</div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatWindow.appendChild(loader);
    scrollToBottom();
    return loader;
}

function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendMessage(sender, htmlContent, typeClass) {
    const msg = document.createElement("div");
    msg.className = `message ${typeClass}`;
    
    msg.innerHTML = `
        <div class="avatar">${sender === 'You' ? '👤' : '🤖'}</div>
        <div class="message-content">
            ${htmlContent}
        </div>
    `;
    
    chatWindow.appendChild(msg);
    scrollToBottom();
}

// --- API Interactions ---

async function handleAsk() {
    const question = questionInput.value.trim();
    if (!question) return;

    questionInput.value = "";
    appendMessage("You", `<div class="message-title">You asked:</div><p>${question}</p>`, "user-message");
    
    const loader = showTypingIndicator();

    try {
        const payload = {
            question: question,
            completed_courses: completedCourses
        };
        
        const response = await fetch(`${API_URL}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        loader.remove();

        if (!response.ok) throw new Error(data.detail || data.error || "Unknown error");

        // Clarifying Question path
        if (data.clarifying_questions) {
            let html = `<div class="message-title">I need more context:</div><ul>`;
            data.clarifying_questions.forEach(q => html += `<li>${q}</li>`);
            html += `</ul>`;
            appendMessage("System", html, "system-message");
            return;
        }

        // Standard AskResponse path
        sourceDataRaw = data.sources || [];
        const isUnknown = data.decision.toLowerCase().includes("unknown");
        let html = `
            <div class="message-title">
                <span>Eligibility Decision</span>
                <span class="latency-badge">${data.latency_ms}ms</span>
            </div>
            
            <div class="message-block">
                <strong>Decision:</strong> <span style="color: ${isUnknown ? 'var(--danger)' : 'var(--accent)'}">${data.decision}</span>
            </div>
            <div class="message-block">
                <strong>Why:</strong> <p>${data.why}</p>
            </div>
        `;

        if (data.next_step) {
            html += `<div class="message-block"><strong>Next Step:</strong> ${data.next_step}</div>`;
        }
        
        if (data.citations && data.citations.length > 0) {
            html += `
                <div class="citations">
                    <strong>Citations:</strong>
                    <ul>${data.citations.map(c => `<li>${c}</li>`).join('')}</ul>
                    ${sourceDataRaw.length > 0 ? `<button class="btn btn-secondary view-sources-btn" onclick="openSourcesModal()">View Context Chunks</button>` : ''}
                </div>
            `;
        }

        appendMessage("System", html, "system-message");

    } catch (error) {
        loader.remove();
        appendMessage("System", `<p style="color: var(--danger)">Error: ${error.message}</p>`, "system-message");
    }
}

async function handlePlan() {
    if (completedCourses.length === 0) {
        alert("Please add at least one completed course first!");
        courseInput.focus();
        return;
    }

    const maxCourses = parseInt(maxCoursesInput.value, 10);
    appendMessage("You", `<div class="message-title">You requested:</div><p>Schedule plan for next term (max ${maxCourses} courses)</p>`, "user-message");
    
    const loader = showTypingIndicator();

    try {
        const payload = {
            completed_courses: completedCourses,
            max_courses: maxCourses
        };
        
        const response = await fetch(`${API_URL}/plan`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        loader.remove();

        if (!response.ok) throw new Error(data.detail || data.error || "Unknown error");

        sourceDataRaw = data.sources || [];
        if (data.suggested_courses.length === 0) {
            appendMessage("System", `<p>${data.risks_assumptions}</p>`, "system-message");
            return;
        }

        let html = `
            <div class="message-title">
                <span>Next Term Plan</span>
                <span class="latency-badge">${data.latency_ms}ms</span>
            </div>
            <div style="margin-bottom: 1rem">
                <em>Assumptions: ${data.risks_assumptions}</em>
            </div>
        `;

        data.suggested_courses.forEach((course, index) => {
            html += `
                <div style="background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem; border-left: 3px solid var(--primary)">
                    <strong style="color: #cbd5e1">${index + 1}. ${course.course}</strong>
                    ${course.title ? ` - <span>${course.title}</span>` : ''}
                    <div style="font-size: 0.875rem; margin-top: 0.5rem; color: var(--text-muted)">
                        <strong>Eligibility:</strong> ${course.eligibility}<br>
                        <strong>Ref:</strong> <em>${course.citation}</em>
                    </div>
                </div>
            `;
        });
        
        html += `
            <div class="citations">
                ${sourceDataRaw.length > 0 ? `<button class="btn btn-secondary view-sources-btn" onclick="openSourcesModal()">View Context Chunks</button>` : ''}
            </div>
        `;

        appendMessage("System", html, "system-message");

    } catch (error) {
        loader.remove();
        appendMessage("System", `<p style="color: var(--danger)">Error: ${error.message}</p>`, "system-message");
    }
}

// Global modal open function attached to buttons rendered dynamically
window.openSourcesModal = function() {
    modalBody.innerHTML = "";
    
    if (sourceDataRaw.length === 0) {
        modalBody.innerHTML = "<p>No raw sources found.</p>";
    } else {
        sourceDataRaw.forEach((chunk, i) => {
            modalBody.innerHTML += `
                <div class="source-chunk">
                    <h4>${chunk.course} <span>Score: ${chunk.score.toFixed(3)}</span></h4>
                    <pre>${chunk.content}</pre>
                </div>
            `;
        });
    }
    
    modal.style.display = "block";
};
