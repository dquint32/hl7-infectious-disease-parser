// HL7 v2 Infectious Disease Parser — browser demo.
// Mirrors the rules of the tested Python package in hl7_infectious/ (LOINC registry,
// v2.5.1 OBX field positions, HL7 table 0078 abnormal flags).

// ---------------------------------------------------------------- i18n
const i18n = {
    en: {
        kicker: "HL7 v2.5.1 · LOINC · Live demo",
        title: "HL7 v2 Infectious Disease Parser",
        subtitle: "Paste an HL7 v2 message or upload a .txt file.",
        parse: "Parse Message",
        summary: "Message Summary",
        parsed: "Parsed Output",
        download: "Download Summary (PDF)",
        input: "Message",
        sample: "Load a sample",
        choose: "Choose a sample message…",
        upload: "Upload .txt file",
        patient: "Patient",
        dob: "DOB",
        empty: "Parse a message to see the patient and results summary."
    },
    es: {
        kicker: "HL7 v2.5.1 · LOINC · Demo en vivo",
        title: "Analizador HL7 v2 para Enfermedades Infecciosas",
        subtitle: "Pegue un mensaje HL7 v2 o cargue un archivo .txt.",
        parse: "Analizar Mensaje",
        summary: "Resumen del Mensaje",
        parsed: "Salida Analizada",
        download: "Descargar Resumen (PDF)",
        input: "Mensaje",
        sample: "Cargar un ejemplo",
        choose: "Elija un mensaje de ejemplo…",
        upload: "Cargar archivo .txt",
        patient: "Paciente",
        dob: "Fecha de nac.",
        empty: "Analice un mensaje para ver el resumen del paciente y los resultados."
    }
};

function setLanguage(lang) {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(el => {
        el.textContent = i18n[lang][el.getAttribute("data-i18n")];
    });
    document.getElementById("enBtn").setAttribute("aria-pressed", String(lang === "en"));
    document.getElementById("esBtn").setAttribute("aria-pressed", String(lang === "es"));
}

document.getElementById("enBtn").onclick = () => setLanguage("en");
document.getElementById("esBtn").onclick = () => setLanguage("es");
// Light/dark theme is handled by the shared dq-theme.js.

// Sample messages shipped in hl-samples/ (synthetic data).
document.getElementById("sampleSelect").addEventListener("change", async function () {
    if (!this.value) return;
    try {
        const res = await fetch(`hl-samples/${encodeURIComponent(this.value)}`);
        if (!res.ok) throw new Error(res.status);
        document.getElementById("hl7Input").value = await res.text();
        document.getElementById("parseBtn").click();
    } catch (err) {
        console.error("Could not load sample:", err);
    }
});

// ---------------------------------------------------------------- reference data
// One registry replaces the separate validLoinc array + nine if-statements.
// Codes verified against loinc.org. 71772-8 is the IGRA mitogen *control*, so it is
// recognised but never reported as a TB result.
const LOINC = {
    "94500-6": { key: "covid", reportable: true },
    "92142-9": { key: "fluA", reportable: true },
    "76078-5": { key: "fluA", reportable: true },
    "92141-1": { key: "fluB", reportable: true },
    "85479-4": { key: "rsv", reportable: true },
    "25836-8": { key: "hiv", reportable: true },
    "64084-7": { key: "tb", reportable: true },
    "45323-3": { key: "tb", reportable: true },
    "71772-8": { key: "tb", reportable: false },
    "13950-1": { key: "hepA", reportable: true },
    "5195-3": { key: "hepB", reportable: true },
    "24113-3": { key: "hepB", reportable: true },
    "13955-0": { key: "hepC", reportable: true }
};

const BADGES = [
    [["covid", "covid", "COVID-19"], ["fluA", "flu", "Flu A"], ["fluB", "flu", "Flu B"]],
    [["rsv", "rsv", "RSV"], ["hiv", "hiv", "HIV VL"], ["tb", "tb", "TB"]],
    [["hepA", "hepA", "Hep A IgM"], ["hepB", "hepB", "Hep B"], ["hepC", "hepC", "Hep C Ab"]]
];

const ABNORMAL_FLAGS = new Set(["L", "H", "LL", "HH", "<", ">", "A", "AA"]); // HL7 table 0078
const CODED_TYPES = new Set(["CE", "CWE", "CNE"]);

// ---------------------------------------------------------------- helpers
const escapeHtml = s => String(s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

// LOINC Mod-10 check digit (same as Luhn).
function isValidLoinc(code) {
    const m = /^(\d{1,7})-(\d)$/.exec(code);
    if (!m) return false;
    let total = 0;
    [...m[1]].reverse().forEach((ch, i) => {
        let d = Number(ch);
        if (i % 2 === 0) { d *= 2; if (d > 9) d -= 9; }
        total += d;
    });
    return (10 - (total % 10)) % 10 === Number(m[2]);
}

function parseMessage(text) {
    const lines = text.split(/\r\n|\r|\n/).filter(l => l.trim());
    if (!lines.length || !lines[0].startsWith("MSH") || lines[0].length < 8) {
        throw new Error("Message must start with an MSH segment.");
    }
    const fieldSep = lines[0][3];
    const [comp, rep] = lines[0].slice(4, 6);
    const component = (value, n) => (value || "").split(rep)[0].split(comp)[n - 1] || "";

    return {
        component,
        segments: lines.map((line, i) => {
            const fields = line.split(fieldSep);
            if (fields[0] === "MSH") fields.splice(1, 0, fieldSep); // keep fields[n] === MSH-n
            return { line: i + 1, name: fields[0], fields };
        })
    };
}

// ---------------------------------------------------------------- parse button
document.getElementById("parseBtn").addEventListener("click", () => {
    const input = document.getElementById("hl7Input").value.trim();
    if (!input) return;

    const outputEl = document.getElementById("output");
    const summaryEl = document.getElementById("summaryBox");

    let msg;
    try {
        msg = parseMessage(input);
    } catch (err) {
        outputEl.innerHTML = `<span class="error">ERROR: ${escapeHtml(err.message)}</span>`;
        summaryEl.innerHTML = "";
        return;
    }

    const { component, segments } = msg;
    const results = {};
    let patientName = "";
    let dob = "";
    let output = "";

    segments.forEach(seg => {
        const f = n => seg.fields[n] || "";
        output += `\n<span class="segment-header">[${escapeHtml(seg.name)}]</span>\n`;

        if (!/^[A-Z][A-Z0-9]{2}$/.test(seg.name)) {
            output += `<span class="error">  ERROR: line ${seg.line} is not a valid HL7 segment</span>\n`;
            return;
        }

        if (seg.name === "PID") {
            patientName = [component(f(5), 2), component(f(5), 1)].filter(Boolean).join(" ");
            dob = f(7);
            if (!component(f(3), 1)) output += `<span class="error">  ERROR: PID-3 patient identifier is missing</span>\n`;
        }

        if (seg.name === "OBX") {
            const loinc = component(f(3), 1);
            const valueType = f(2);
            const value = CODED_TYPES.has(valueType)
                ? component(f(5), 2) || component(f(5), 1)
                : component(f(5), 1);
            const flag = component(f(8), 1);
            const abnormal = ABNORMAL_FLAGS.has(flag);

            if (!isValidLoinc(loinc)) {
                output += `<span class="error">  ERROR: OBX-3 invalid LOINC code → ${escapeHtml(loinc)}</span>\n`;
            } else if (!LOINC[loinc]) {
                output += `<span class="error">  WARNING: LOINC ${escapeHtml(loinc)} not in infectious-disease registry</span>\n`;
            }
            if (!value) output += `<span class="error">  ERROR: OBX-5 result value is missing</span>\n`;
            if (valueType === "NM" && value && Number.isNaN(Number(value))) {
                output += `<span class="error">  ERROR: OBX-5 is not numeric (OBX-2 = NM)</span>\n`;
            }

            const entry = LOINC[loinc];
            if (entry && entry.reportable && value) {
                // Keep an abnormal result rather than letting a later normal one overwrite it.
                const prev = results[entry.key];
                if (!prev || !prev.abnormal || abnormal) results[entry.key] = { value, abnormal };
            }
            if (abnormal) {
                output += `  OBX-5 result: <span class="abnormal">${escapeHtml(value)}</span>\n`;
                output += `  OBX-8 flag:   <span class="abnormal">${escapeHtml(flag)}</span>\n`;
            }
        }

        seg.fields.forEach((field, n) => {
            if (n === 0 || field === "") return;
            output += `  ${escapeHtml(seg.name)}-${n}: ${escapeHtml(field)}\n`;
        });
    });

    const badge = ([key, cls, label]) => {
        const r = results[key];
        const text = r ? escapeHtml(r.value) : "N/A";
        const state = !r ? " is-empty" : r.abnormal ? " is-abnormal" : "";
        return `<span class="badge ${cls}${state}"><span class="badge-label">${label}</span> ${r && r.abnormal ? `<strong>${text}</strong>` : text}</span>`;
    };

    const t = i18n[document.documentElement.lang === "es" ? "es" : "en"];
    summaryEl.innerHTML = `
<div class="summary-meta"><div class="summary-line"><span class="meta-label">${t.patient}</span> <strong>${escapeHtml(patientName)}</strong></div>
<div class="summary-line"><span class="meta-label">${t.dob}</span> <strong>${escapeHtml(dob)}</strong></div></div>
${BADGES.map(row => `<div class="badge-row">${row.map(badge).join("")}</div>`).join("\n")}`;

    outputEl.innerHTML = output;
    outputEl.scrollTop = outputEl.scrollHeight;
});

// ---------------------------------------------------------------- file upload & print
document.getElementById("fileInput").addEventListener("change", function () {
    const file = this.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => { document.getElementById("hl7Input").value = e.target.result; };
    reader.readAsText(file);
});

document.getElementById("downloadBtn").addEventListener("click", () => window.print());
