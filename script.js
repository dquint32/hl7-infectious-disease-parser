// Bilingual dictionary
const i18n = {
    en: {
        title: "HL7 v2 Infectious Disease Parser",
        subtitle: "Paste an HL7 v2 message or upload a .txt file.",
        parse: "Parse Message",
        summary: "Message Summary",
        parsed: "Parsed Output",
        download: "Download Summary (PDF)"
    },
    es: {
        title: "Analizador HL7 v2 para Enfermedades Infecciosas",
        subtitle: "Pegue un mensaje HL7 v2 o cargue un archivo .txt.",
        parse: "Analizar Mensaje",
        summary: "Resumen del Mensaje",
        parsed: "Salida Analizada",
        download: "Descargar Resumen (PDF)"
    }
};

// Language toggle
function setLanguage(lang) {
    document.querySelectorAll("[data-i18n]").forEach(el => {
        el.textContent = i18n[lang][el.getAttribute("data-i18n")];
    });
}

document.getElementById("enBtn").onclick = () => setLanguage("en");
document.getElementById("esBtn").onclick = () => setLanguage("es");

// Dark mode toggle
const darkToggle = document.getElementById("darkToggle");
darkToggle.addEventListener("click", () => {
    document.body.classList.toggle("dark");
});

// LOINC codes for validation
const validLoinc = [
    "94500-6", // COVID PCR
    "92141-1", // Flu A/B PCR
    "25836-8", // HIV Viral Load
    "76078-5", // RSV
    "71772-8", "64084-7", "45323-3", // TB Quantiferon
    "13950-1", // Hep A IgM
    "5195-3", "24113-3", // Hep B
    "13955-0" // Hep C Ab
];

document.getElementById("parseBtn").addEventListener("click", () => {
    const input = document.getElementById("hl7Input").value.trim();
    if (!input) return;

    const segments = input.split("\n");
    let output = "";
    let patientName = "";
    let dob = "";

    // Disease summary variables
    let covid = "";
    let fluA = "";
    let fluB = "";
    let rsv = "";
    let hiv = "";
    let tb = "";
    let hepA = "";
    let hepB = "";
    let hepC = "";

    segments.forEach(seg => {
        const fields = seg.split("|");
        const segmentName = fields[0];

        // Color-coded segment header
        output += `\n<span class="segment-header">[${segmentName}]</span>\n`;

        // Missing field detection
        if (fields.length < 2) {
            output += `<span class="error">  ERROR: Missing required fields</span>\n`;
        }

        // PID summary extraction
        if (segmentName === "PID") {
            patientName = fields[5]?.replace("^", " ") || "";
            dob = fields[7] || "";
        }

        // OBX logic
        if (segmentName === "OBX") {
            const loinc = fields[3]?.split("^")[0] || "";
            const testName = fields[3] || "";
            const result = fields[5] || "";
            const abnormalFlag = fields[7] || "";

            // LOINC validation
            if (loinc && !validLoinc.includes(loinc)) {
                output += `<span class="error">  ERROR: Invalid LOINC code → ${loinc}</span>\n`;
            }

            // Disease detection
            if (loinc === "94500-6") covid = result; // COVID
            if (testName.includes("Influenza A")) fluA = result; // Flu A
            if (testName.includes("Influenza B")) fluB = result; // Flu B
            if (loinc === "76078-5") rsv = result; // RSV
            if (loinc === "25836-8") hiv = result; // HIV VL
            if (["71772-8", "64084-7", "45323-3"].includes(loinc)) tb = result; // TB
            if (loinc === "13950-1") hepA = result; // Hep A IgM
            if (loinc === "5195-3" || loinc === "24113-3") hepB = result; // Hep B
            if (loinc === "13955-0") hepC = result; // Hep C Ab

            // Abnormal highlighting
            if (abnormalFlag === "A") {
                output += `  Field 5: <span class="abnormal">${result}</span>\n`;
                output += `  Field 7: <span class="abnormal">${abnormalFlag}</span>\n`;
            }
        }

        // Print all fields normally
        fields.forEach((field, index) => {
            if (index === 0) return;
            output += `  Field ${index}: ${field}\n`;
        });
    });

    // Summary box with disease badges
    const summaryHtml = `
<div class="summary-line"><strong>Patient:</strong> ${patientName}</div>
<div class="summary-line"><strong>DOB:</strong> ${dob}</div>

<div class="badge-row">
  <span class="badge covid">🦠 COVID-19: ${covid || "N/A"}</span>
  <span class="badge flu">🤧 Flu A: ${fluA || "N/A"}</span>
  <span class="badge flu">🤧 Flu B: ${fluB || "N/A"}</span>
</div>

<div class="badge-row">
  <span class="badge rsv">👶 RSV: ${rsv || "N/A"}</span>
  <span class="badge hiv">🧬 HIV VL: ${hiv || "N/A"}</span>
  <span class="badge tb">🫁 TB: ${tb || "N/A"}</span>
</div>

<div class="badge-row">
  <span class="badge hepA">🩸 Hep A IgM: ${hepA || "N/A"}</span>
  <span class="badge hepB">🩸 Hep B: ${hepB || "N/A"}</span>
  <span class="badge hepC">🩸 Hep C Ab: ${hepC || "N/A"}</span>
</div>
`;

    document.getElementById("summaryBox").innerHTML = summaryHtml;

    // Render parsed output (HTML allowed)
    const outputEl = document.getElementById("output");
    outputEl.innerHTML = output;

    // Auto-scroll to bottom
    outputEl.scrollTop = outputEl.scrollHeight;
});

// Load file into textarea
document.getElementById("fileInput").addEventListener("change", function () {
    const file = this.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (e) {
        document.getElementById("hl7Input").value = e.target.result;
    };
    reader.readAsText(file);
});

// Download summary as PDF (simple print-to-PDF approach)
document.getElementById("downloadBtn").addEventListener("click", () => {
    window.print();
});
