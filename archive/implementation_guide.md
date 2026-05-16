## Overview

This guide provides the step-by-step instructions to implement the automated document generation system as designed by the Architect. The process involves setting up SharePoint, creating a Word template and a Microsoft Form, and finally building a Power Automate flow to orchestrate the entire workflow.

### Prerequisites

1.  **Microsoft 365 Subscription:** Your organization needs a subscription that includes SharePoint, Microsoft Forms, and Power Automate.
2.  **Premium Power Automate License:** This solution **requires** the "Populate a Microsoft Word template" action, a Premium Connector. Before you begin, confirm with your M365 administrator that you have a license which includes this capability (e.g., a Power Automate per-user plan or a qualifying Dynamics 365/Power Apps license). The project cannot proceed without it.
3.  **Permissions:** You must have sufficient permissions to create a SharePoint Document Library, a Microsoft Form, and a Power Automate flow.

---

## Step 1: SharePoint Folder Setup

First, we establish the central repository for our template and generated reports in SharePoint.

1.  Navigate to the target SharePoint site.
2.  Open the default "Documents" library or create a new Document Library.
3.  Create a new folder named `BatteryMaintenanceReports`.
4.  Inside the `BatteryMaintenanceReports` folder, create two subfolders:
    *   `_Templates`
    *   `GeneratedReports`

The final structure will be:
`/documents/BatteryMaintenanceReports/_Templates/`
`/documents/BatteryMaintenanceReports/GeneratedReports/`

The `GeneratedReports` folder will be populated with year-specific subfolders automatically by the flow.

---

## Step 2: Create the Word Template with Content Controls

This is the master document. Power Automate will use "Content Controls" as placeholders to insert data and images. **This step must be done in the Word desktop app.**

1.  **Enable the Developer Tab in Word:**
    *   Open the Word desktop app.
    *   Go to `File` > `Options` > `Customize Ribbon`.
    *   On the right side, under "Main Tabs," check the box for `Developer` and click `OK`.

2.  **Design the Report and Insert Controls:**
    *   Create a new, blank document.
    *   Lay out your report's static content (titles, headers, tables, etc.).
    *   Place your cursor where dynamic data should appear.
    *   From the **Developer** tab:
        *   Click the **"Plain Text Content Control"** icon for text fields.
        *   Click the **"Picture Content Control"** icon for the image.

3.  **Configure Control Properties:**
    *   For each control you add, select it and click **"Properties"** from the Developer tab's "Controls" group.
    *   In the **Title** field, enter a simple, one-word name. This name is the internal ID that Power Automate will use. **Do not use spaces or special characters.**
    *   Click `OK`.

    **Example Control Configuration:**

    | Placeholder in Document       | Control Type              | Title Property Name |
    | ----------------------------- | ------------------------- | ------------------- |
    | e.g., Site: `[Site]`          | Plain Text Content Control| `SiteName`          |
    | e.g., Technician: `[Name]`    | Plain Text Content Control| `TechnicianName`    |
    | e.g., Date: `[Date]`          | Plain Text Content Control| `DateOfService`     |
    | e.g., Battery ID: `[ID]`      | Plain Text Content Control| `BatteryID`         |
    | e.g., Observations: `[Notes]` | Plain Text Content Control| `Observations`      |
    | `[Photo Placeholder box]`     | Picture Content Control   | `SitePhoto`         |

4.  **Save and Upload:**
    *   Save the document with the filename `Battery_Maintenance_Template.docx`.
    *   Upload this file to the SharePoint folder you created: `/BatteryMaintenanceReports/_Templates/`.

---

## Step 3: Create the Microsoft Form

This form will serve as the data entry point for technicians.

1.  Navigate to Microsoft Forms ([forms.office.com](https://forms.office.com)).
2.  **Crucial:** To use the "File Upload" feature, you must create the form within a Microsoft 365 Group/Team. Click "New Group Form" and select the appropriate group. This ensures uploaded files are stored in the group's SharePoint site, making them accessible to Power Automate. A personal form will not work reliably.
3.  Click **"New Form"**.
4.  Add questions corresponding to your Word template's controls:
    *   **Site Name:** Text question (set to **Required**).
    *   **Technician Name:** Text question (set to **Required**).
    *   **Date of Service:** Date question (set to **Required**).
    *   **Battery ID:** Text question (set to **Required**).
    *   **Observations:** Text question (enable "Long answer").
    *   **Site Photo:** Use the `+ Add new` > `(More question types)` > **`File Upload`** question.
        *   A message will appear about files being stored in SharePoint; click OK.
        *   Set the "File number limit" to `1`.
        *   Set the toggle for **Required** to `On`.
        *   Optionally, restrict "File type" to `Image`.

---

## Step 4: Build the Power Automate Flow

This flow automates the process from form submission to report generation.

1.  Navigate to Power Automate ([make.powerautomate.com](https://make.powerautomate.com)).
2.  Go to **Create** > **Automated cloud flow**.
3.  Name your flow (e.g., `Generate Battery Maintenance Report`).
4.  For the trigger, search and select **"When a new response is submitted"** (from Microsoft Forms), and click **Create**.

### Flow Configuration

**1. Trigger: When a new response is submitted**
*   **Form Id:** Select the "Battery Maintenance Report" form you created.

**2. Action: Get response details**
*   Click `+ New step`.
*   Search for and add the **"Get response details"** action (from Microsoft Forms).
*   **Form Id:** Select the same form again.
*   **Response Id:** Click the field, and in the "Dynamic content" pane, select **"Response Id"** from the trigger step.

**3. Action: Parse JSON (for Image)**
*   Click `+ New step`.
*   Search for and add the **"Parse JSON"** action (a Data Operation). This is needed to properly read the file upload information.
*   **Content:** From the Dynamic content pane, select the **"Site Photo"** question (or whatever you named your file upload question).
*   **Schema:** Click the **"Generate from sample"** button. Paste the following JSON structure into the text box and click **Done**. This teaches the flow the structure of the file upload data.
    ```json
    [
        {
            "name": "sample.jpg",
            "link": "https://...",
            "id": "...",
            "type": null,
            "size": 12345,
            "referenceId": "...",
            "driveId": "...",
            "status": 1,
            "uploadSessionUrl": null
        }
    ]
    ```

**4. Action: Get file content**
*   Click `+ New step`.
*   Search for and add the **"Get file content"** action (from **SharePoint**).
    *   **Important Note:** You must use the SharePoint connector. Because we used a Group Form, the uploaded file lives in the Group's SharePoint site, *not* the submitter's OneDrive.
*   **Site Address:** Select the SharePoint site associated with the Microsoft 365 Group where you created the form.
*   **File Identifier:** This field needs the unique ID of the file. Click in the field, switch to the **Expression** tab in the Dynamic Content popup, and paste the following expression. This retrieves the ID of the first (and only) uploaded file from the previous step.
    ```
    body('Parse_JSON')?[0]?['id']
    ```

**5. Action: Populate a Microsoft Word template (Premium)**
*   Click `+ New step`.
*   Search for and add the **"Populate a Microsoft Word template"** action (from Word Online (Business)).
*   **Location:** Select your SharePoint site where the template is stored.
*   **Document Library:** Select "Documents".
*   **File:** Use the file picker to navigate to and select your template: `/BatteryMaintenanceReports/_Templates/Battery_Maintenance_Template.docx`.
*   The action will refresh and display fields for each Content Control you created. Map them using the Dynamic content pane:
    *   `SiteName`: Select **"Site Name"** from "Get response details".
    *   `TechnicianName`: Select **"Technician Name"**.
    *   `DateOfService`: Select **"Date of Service"**.
    *   `BatteryID`: Select **"Battery ID"**.
    *   `Observations`: Select **"Observations"**.
    *   `SitePhoto`: Select **"File Content"** from the "Get file content" step.

**6. Action: Create file**
*   Click `+ New step`.
*   Search for and add the **"Create file"** action (from **SharePoint**).
*   **Site Address:** Select your SharePoint site.
*   **Folder Path:** To save files into year-based folders, enter this path exactly. SharePoint will create the year folder if it doesn't exist.
    ```
    /BatteryMaintenanceReports/GeneratedReports/@{formatDateTime(utcNow(), 'yyyy')}
    ```
*   **File Name:** To create a unique, timestamped filename, click the field, switch to the **Expression** tab, and enter:
    ```
    concat('Battery_Report_', formatDateTime(utcNow(), 'yyyy-MM-dd-HH-mm-ss'), '.docx')
    ```
*   **File Content:** Select **"Microsoft Word Document"** from the "Populate a Microsoft Word template" step.

---

### Finalization

1.  **Save** your flow in the top-right corner.
2.  **Test** the entire process by filling out and submitting the Microsoft Form.
3.  Navigate to your SharePoint site and check the `/BatteryMaintenanceReports/GeneratedReports/` folder. A new folder for the current year should exist, containing your completed `.docx` report.