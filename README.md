# HL7 v2 Infectious Disease Parser

## Project Overview
This application is a specialized parsing tool designed for healthcare data analysts and clinical informatics professionals. It focuses on **HL7 v2 ORU (Observation Result)** messages, specifically those related to infectious disease reporting (COVID-19, Flu, HIV, etc.). 

The tool provides a user-friendly interface to convert raw, pipe-delimited HL7 strings into a readable format with automated medical logic validation.

---

## 🛠 Key Features
* **Bilingual Support (EN | ES)**: Fully localized interface for English and Spanish speakers.
* **LOINC Validation**: Cross-references result codes against a built-in dictionary of valid infectious disease LOINC codes (e.g., 94500-6 for COVID PCR).
* **Automated Disease Summary**: Extracts patient demographics and specific test results to display visual status badges.
* **Error & Abnormal Detection**: 
    * Highlights missing required fields in red.
    * Visual "Abnormal" flags for clinical alerts.
* **Dark Mode**: Optimized for high-contrast viewing in clinical environments.
* **PDF Export**: Allows users to download a summary of the parsed results.

---

## 🏗 Technical Implementation
* **Vanilla JavaScript**: Handles all parsing logic, regex-based extraction, and DOM updates without external dependencies.
* **CSS3 Variables**: Drives the theme engine for seamless switching between Light and Dark modes.
* **HTML5 File API**: Enables direct uploading of `.txt` files containing HL7 messages.

---

## 📂 File Structure
* `index.html`: The semantic structure including the language toggle and output containers.
* `script.js`: The "brain" of the app containing the i18n dictionary, LOINC validation list, and parsing logic.
* `style.css`: Professional medical-themed styling and responsive layout.
* `parser.py`: A Python-based alternative parser utilizing the `hl7apy` library for backend or command-line environments.

---

## 🎓 Academic Purpose
<section id="purpose">
    <h3>Purpose of This Site</h3>
    <p>This website was created in partial fulfillment of the CIS 3030 course requirements at MSU Denver.</p>
    <dl>
        <dt>Student Developer</dt>
        <dd>David Quintana</dd>
        <dt>Contact</dt>
        <dd>dquint32@msudenver.edu</dd>
        <dt>Language Preference</dt>
        <dd>English | Spanish</dd>
        <dt>Course Info</dt>
        <dd>CIS 3030 - Web Development</dd>
    </dl>
</section>

---

## 🚀 How to Use
1.  Open `index.html` in any browser.
2.  Paste a raw HL7 v2 message into the text area or upload a `.txt` file.
3.  Click **"Parse Message"**.
4.  Review the **Patient Summary** badges and the detailed **Parsed Output**.
5.  Use the **"Download Summary"** button to save the result as a PDF.

---

**Disclaimer:** This tool is for educational purposes. Always ensure HIPAA compliance and use de-identified data for testing.
