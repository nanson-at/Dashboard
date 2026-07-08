# Implementation Plan - Dashboard Refresh and Route Additions (205E Kam Sheung Road Area)

This plan outlines changes to `index.html` to update data every 10 seconds, configure bus routes (**251A**, **64K**) and green minibus (GMB) routes (**71**, **71A**) near the user's location at **205E Kam Sheung Road** (using the Shek Wu Tong and Win Gain Garden stops), and rewrite rendering logic to use secure DOM manipulation instead of `innerHTML` to prevent XSS vulnerability risks.

## Proposed Changes

### Dashboard Frontend

#### [MODIFY] [index.html](file:///c:/Users/Anson/OneDrive/Documents/Dashboard/index.html)

- **Update Frequency**: Change the update intervals for bus and weather data from 60 seconds (60000ms) to 10 seconds (10000ms).
- **CSS Styling**:
  - Add styles for `.bus-route-container` and `.bus-dest` to display route destinations cleanly below the route number.
  - Adjust `.bus-row` and `.weather-row` vertical paddings to support displaying all 7 routes/directions in the fixed-height viewport.
- **Route configuration near 205E Kam Sheung Road**:
  - **KMB 251A** (往上村): Stop `7AA3F7F89AD36B1B` (石湖塘 YL659)
  - **KMB 64K** (往大埔墟站): Stop `7AA3F7F89AD36B1B` (石湖塘 YL659)
  - **KMB 64K** (往元朗西): Stop `3D29F886079F85E9` (石湖塘 YL694)
  - **GMB 71** (往河背): Stop `20016485` (石田路, 近威裕花園)
  - **GMB 71** (往元朗): Stop `20016474` (石田路, 近威裕花園)
  - **GMB 71A** (往長莆): Stop `20016485` (石田路, 近威裕花園)
  - **GMB 71A** (往錦上路站): Stop `20016474` (石田路, 近威裕花園)
- **API Fetching & Parsing**:
  - Implement a parallel fetching mechanism using `Promise.allSettled` to query the respective KMB and GMB API endpoints.
  - Parse KMB stop-eta responses and GMB route-stop ETA responses.
- **Secure DOM Manipulation**:
  - Replace the vulnerable `innerHTML` assignments with modern, safe DOM APIs (`document.createElement`, `textContent`, `appendChild`, and `replaceChildren`) to comply with secure coding practices and eliminate XSS risks.

## Verification Plan

### Automated Tests
- Since this is a static HTML page relying on browser APIs, we can perform manual verification.

### Manual Verification
- Open [index.html](file:///c:/Users/Anson/OneDrive/Documents/Dashboard/index.html) in a browser.
- Verify that the layout remains clean and readable with all 7 configured routes/directions.
- Open the browser Developer Console and inspect network requests to verify that requests to `data.etabus.gov.hk` and `data.etagmb.gov.hk` are fired every 10 seconds.
- Verify that the ETAs for 251A, 64K, 71, and 71A are correctly parsed and rendered.

### Security Verification
- Verify that all DOM manipulation is done via `textContent` and `createElement` instead of `innerHTML`.
