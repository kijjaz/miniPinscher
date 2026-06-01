# miniPinscher: Google Sheets Fragrance Compliance Suite (v0.6.1) 🐕‍🦺

This directory contains the custom Apps Script code and reference database files to run full **IFRA 51st Amendment Safety Checks** and **EU 2023/1545 Allergen Labeling** directly inside Google Sheets.

---

## 📂 Package Directory Structure

1.  `Code.js`: The custom Google Apps Script containing the logic for `=IFRA_COMPLIANCE_V5` and `=EU_LABELING_V5`.
2.  `DB_Standards.csv`: Master list of official IFRA restricted materials, CAS numbers, and Category 4 limits.
3.  `DB_Naturals.csv`: Annex I compositions (essential oil constituents) to calculate indirect exposures automatically.
4.  `DB_Inventory.csv`: Stock name alias mapping (Stock Name -> Official IFRA Name) to handle trade names.
5.  `DB_User_Materials.csv`: Your personal bases and dilutions database (5,049 rows of constituents).
6.  `DB_EU_Allergens.csv`: EU 2023/1545 official INCI allergen list.

---

## 🛠️ Onboarding & Setup Instructions (English)

### Step 1: Import Reference Databases into Google Sheets
Create a new tab/sheet for each reference file and import the data:
1.  Open your Google Sheet.
2.  Go to **File** > **Import** > **Upload** and upload each CSV file into its own tab:
    - Tab Name: `DB_Standards`
    - Tab Name: `DB_Naturals`
    - Tab Name: `DB_Inventory`
    - Tab Name: `DB_User_Materials`
    - Tab Name: `DB_EU_Allergens`

### Step 2: Install the Custom App Script Code
1.  Open `Code.js` in a text editor and copy all the text.
2.  In Google Sheets, go to **Extensions** > **Apps Script**.
3.  Delete any existing code in the editor, paste the copied text, and click the **Save** icon (disk symbol).
4.  Close the Apps Script window.

### Step 3: Run the Custom Calculations

#### (A) Check IFRA Compliance
To run a full IFRA check on a formula (e.g., in columns `A` and `B`):
```excel
=IFRA_COMPLIANCE_V5(A2:B, DB_Standards!A2:C, DB_Naturals!A2:D, DB_Inventory!A2:B, DB_User_Materials!A2:E)
```

#### (B) Check EU 2023/1545 Allergen Labeling Requirements
To automatically calculate which allergens must be listed on the product label:
```excel
=EU_LABELING_V5(A2:B, DB_EU_Allergens!A2:B, DB_Naturals!A2:D, DB_Inventory!A2:B, DB_User_Materials!A2:E, "Leave-on")
```
*Tip: Change `"Leave-on"` to `"Rinse-off"` for rinse-off product regulations.*

---

## 🛠️ คู่มือการติดตั้งภาษาไทย (Thai Guide)

### ขั้นตอนที่ 1: นำเข้าฐานข้อมูลเข้าสู่ Google Sheets
สร้างแผ่นงาน (Tab) ใหม่ใน Google Sheet สำหรับแต่ละไฟล์เพื่อใช้อ้างอิง:
1.  ไปที่ **ไฟล์ (File)** > **นำเข้า (Import)** > **อัปโหลด (Upload)**
2.  นำเข้าแต่ละไฟล์แยกตามชื่อ Tab ดังนี้:
    - ชื่อ Tab: `DB_Standards` (มาตรฐาน IFRA)
    - ชื่อ Tab: `DB_Naturals` (น้ำมันหอมระเหยในธรรมชาติ)
    - ชื่อ Tab: `DB_Inventory` (สต็อก/ชื่อเรียกเฉพาะ)
    - ชื่อ Tab: `DB_User_Materials` (เบสและการเจือจางวัตถุดิบ)
    - ชื่อ Tab: `DB_EU_Allergens` (รายชื่อสารก่อภูมิแพ้ EU INCI)

### ขั้นตอนที่ 2: ติดตั้งสคริปต์คำนวณอัตโนมัติ
1.  เปิดไฟล์ `Code.js` คัดลอกโค้ดทั้งหมด
2.  ใน Google Sheet ไปที่ **ส่วนขยาย (Extensions)** > **Apps Script**
3.  ลบโค้ดเดิมทั้งหมดออก แล้ววางโค้ดที่คัดลอกมาลงไป จากนั้นกดปุ่ม **บันทึก (Save)** (รูปแผ่นดิสก์)
4.  ปิดหน้าต่าง Apps Script

### ขั้นตอนที่ 3: เริ่มใช้งานสูตรคำนวณ

#### (ก) ตรวจสอบความถูกต้องตามมาตรฐาน IFRA:
กรอกสูตรนี้ในแผ่นงานของคุณ (โดย `A2:B` คือช่วงที่กรอกชื่อวัตถุดิบและปริมาณ):
```excel
=IFRA_COMPLIANCE_V5(A2:B, DB_Standards!A2:C, DB_Naturals!A2:D, DB_Inventory!A2:B, DB_User_Materials!A2:E)
```

#### (ข) ตรวจสารก่อภูมิแพ้ที่ต้องแสดงบนฉลาก (EU Allergen Labeling):
ตรวจสอบรายชื่อสารเคมีที่เกินค่าขีดจำกัด (Leave-on: 0.001% / Rinse-off: 0.01%):
```excel
=EU_LABELING_V5(A2:B, DB_EU_Allergens!A2:B, DB_Naturals!A2:D, DB_Inventory!A2:B, DB_User_Materials!A2:E, "Leave-on")
```
*(เปลี่ยนคำว่า `"Leave-on"` เป็น `"Rinse-off"` หากเป็นผลิตภัณฑ์กลุ่มสบู่/ล้างออก)*
