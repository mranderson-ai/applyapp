# Visual Design & Typographic Specification for Executive Resumes & Cover Letters

This is a standalone world-class **Visual Design & Typographic Specification**.

This document is designed to act as a system-level design prompt for a downstream LLM, document generation script, or rendering pipeline (such as HTML/CSS-to-PDF or Word template engine) after textual content has already been generated. It resolves the tension between ATS parsing safety and executive-level human readability.

## 1. System Architecture & Rendering Objectives

The primary objective of this visual specification is to enforce elite typographic hierarchy, scanning friction reduction, and aesthetic elegance without introducing visual constructs that trigger Applicant Tracking System (ATS) parsing errors. Downstream document rendering agents must consume pre-drafted text and apply the formatting, whitespace, typography, and structural grid rules detailed below.

## 2. Document Layout, Grid & Page Parameters

| Parameter | Specification | Technical Constraints & Anti-Patterns |
| --- | --- | --- |
| Page Dimensions | US Letter (8.5 in x 11.0 in / 215.9 mm x 279.4 mm) for US/Canada. | Avoid A4 conversions for US applications to prevent accidental margin clipping. |
| Document Margins | Uniform 0.6 in (43.2 pt) or 0.75 in (54 pt) on all four sides. | Never drop below 0.5 in (causes text clipping in PDF rendering). Never exceed 1.0 in. |
| Grid Column Structure | Single-column, linear, top-to-bottom layout flow. | Absolute prohibition on multi-column grids, sidebars, floating text boxes, or CSS flex/grid structures. |
| Text Alignment | Left-aligned (ragged right) for all body text, bullet lists, and section headers. | Avoid full justification (creates irregular "rivers" of white space between words that degrade readability). |
| Page Target Budgeting | Strict 1-page budget for entry/mid-level; strict 2-page budget for 10+ years of experience. | Never generate a document ending in a "trailing orphan page" (less than 25% full page). |

## 3. Typographic System & Hierarchy Scale

To guarantee cross-platform rendering consistency across Mac, Windows, Linux, and web-based PDF previewers, rendering engines must utilize web-safe system font families.

### Approved Typeface Families

- **Sans-Serif (Modern / Executive)**: Calibri (Primary), Arial, or Helvetica.
- **Serif (Classic / Institutional)**: Georgia or Garamond.

### Modular Typographic Scale

Document Title / Candidate Name: 18pt to 20pt (Bold)

Section Headings (H1): 12pt to 13pt (Bold, ALL CAPS)

Job Titles & Companies (H2): 11pt (Bold or Semi-Bold)

Location & Date Metadata: 10.5pt to 11pt (Italic or Muted Regular)

Body Text & Bullet Points: 10pt to 10.5pt (Regular)

| Text Level | Size | Weight | Case / Style | Function & Spatial Placement |
| --- | --- | --- | --- | --- |
| Candidate Name | 18pt – 20pt | Bold | Title Case | Top anchor of Document Header; centered or left-aligned. |
| Contact Metadata | 10pt – 10.5pt | Regular | Sentence / Lowercase | Sub-header block immediately below candidate name. |
| Section Headings (H1) | 12pt – 13pt | Bold | ALL CAPS | Major structural signposts (WORK EXPERIENCE, EDUCATION, SKILLS). |
| Organization Name | 11pt | Bold | Title Case | Primary lead line for employment entries; left-aligned. |
| Job Title | 11pt | Semi-Bold / Italic | Title Case | Placed inline with or directly below Organization Name. |
| Dates & Location | 10.5pt – 11pt | Regular / Italic | Standard (MM/YYYY – Present) | Right-aligned on the same line as Organization/Title line. |
| Body / Bullet Text | 10pt – 10.5pt | Regular | Sentence Case | Narrative summary blocks and bulleted achievement lists. |

## 4. Vertical Whitespace & Micro-Spacing Rules

Whitespace acts as a functional design element that establishes vertical cadence, signals structural changes, and prevents visual fatigue during human scanning.

- **Line Height (Leading)**:
  - **Body & Bullet Text**: Set to 1.10x – 1.15x font size (115% / 12pt leading for 10pt font).
  - **Section Headings**: Set to 1.20x – 1.25x font size.
- **Inter-Element Vertical Margins**:
  - **Space Before Section Headings (H1)**: 8pt to 10pt gap above the heading to separate historical blocks cleanly.
  - **Space After Section Headings (H1)**: 3pt to 4pt gap below heading before content starts.
  - **Space Between Role Entries**: 6pt to 8pt gap between distinct corporate positions.
  - **Space After Individual Bullet Points**: 2pt to 3pt padding after each bullet point group to keep multi-line lists readable.

## 5. Visual Hierarchy & Structural Styling Protocols

### Horizontal Divider Rules

- Place a thin horizontal rule (0.5pt to 0.75pt stroke) directly under major Section Headings (H1).
- **Color Spec**: Solid dark neutral (e.g., #222222 charcoal or #1A365D deep navy).
- **Implementation Rule**: Must be rendered via paragraph borders or inline rule structures (`<hr>`), never as an inserted graphic image or floating line shape.

### Bullet List Formatting & Indentation

- **Bullet Symbol**: Use standard solid round bullet points (•, Unicode U+2022) or simple hyphens (-). Prohibit custom arrows, checkmarks, or graphic icons.
- **Indent Spec**: Left margin indent of 0.15 in to 0.20 in for bullet glyphs; text hanging indent aligned precisely at 0.30 in.
- **Character Budget per Line**: Maintain 70 to 85 characters per line to optimize eye tracking during human scanning.

### Color Palette Constraints

- **Primary Text**: Deep Off-Black / Charcoal (#111111 or #1A1A1A) for higher contrast than pure black without visual harshness.
- **Accent Color (Optional for Headings & Lines)**: Muted Executive Navy (#1B365D or #0F2C59) or Dark Slate (#2C3E50). Avoid bright or pastel tones.

## 6. Cover Letter Layout & Formatting Blueprint

The cover letter must act as a visual companion to the resume, sharing identical margin grids, typography scales, header formatting, and color palettes.

```
================================================================================
CANDIDATE NAME
City, State | Phone | Email | LinkedIn URL
================================================================================
[Space: 12pt]
Date (e.g., October 24, 2026)
[Space: 10pt]
Hiring Manager Name / Title
Target Organization Name
Company Street Address or City, State
[Space: 12pt]
RE: Application for [Target Position Title] - [Requisition ID]
[Space: 12pt]
Dear [Hiring Manager Name / Selection Committee],
[Space: 8pt]
[Paragraph 1: Executive Opening & Core Value Proposition]
[Space: 8pt]
[Paragraph 2: Key Accomplishments & Technical Alignment]
[Space: 8pt]
[Paragraph 3: AI / Operational Impact & Strategic Fit]
[Space: 8pt]
[Paragraph 4: Closing & Actionable Call to Conversation]
[Space: 12pt]
Sincerely,
[Space: 18pt - Signature Gap]
Candidate Name
================================================================================
```

### Cover Letter Specifics

- **Line Height**: 1.15x for narrative paragraphs.
- **Paragraph Spacing**: Left-aligned, un-indented block paragraphs with an 8pt gap between paragraphs.
- **Length**: Strictly 1 page (250 to 375 words max).

## 7. ATS-Safe Rendering Rules & Technical Constraints

To ensure 100% ingestion accuracy across enterprise parsers (Textkernel, Sovren, Eightfold, Workday, Taleo), rendering agents must follow these hard technical rules:

1. **No Text Boxes or Floating Frames**: Contact information, summaries, and skills must exist in the primary document body text stream.
2. **No Visual Tables for Layout Alignment**: Tables scramble text reading orders in up to 84% of ATS parsers. Align dates and locations using tab stops or inline flex-space formatting.
3. **No Header/Footer Embeddings**: All candidate metadata (Name, Phone, Email, Location) must sit in the main body layer at the top of Page 1.
4. **Standard Section Heading Taxonomy**: Section headings must strictly use standard terms: WORK EXPERIENCE, PROFESSIONAL EXPERIENCE, EDUCATION, CORE COMPETENCIES, or TECHNICAL SKILLS.
5. **PDF File Structure**: When exporting to PDF, the rendering pipeline must generate a text-selectable vector PDF (PDF/A compliant) with embedded standard fonts, never a rasterized or image-flattened PDF.
