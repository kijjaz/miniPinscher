/**
 * IFRA Compliance Engine for Google Sheets (V5 - Phototoxicity & Isomer Aggregation)
 * 
 * Paste this into Extensions > Apps Script
 */

/**
 * Checks IFRA Compliance including Source Tracing, Isomer Aggregation, and Phototoxicity.
 * 
 * Usage: 
 * =IFRA_COMPLIANCE_V5(FormulaRange, StandardsRange, NaturalsRange, InventoryRange, UserMaterialsRange, FinishedDosage)
 * 
 * Example:
 * =IFRA_COMPLIANCE_V5(A2:B, DB_Standards!A2:C, DB_Naturals!A2:D, DB_Inventory!A2:B, DB_User_Materials!A2:E, 20)
 * 
 * @param {Array<Array<string|number>>} formula The formula range (Name, Amount).
 * @param {Array<Array<string|number>>} standardsTable The IFRA Standards data (Name, CAS, Limit).
 * @param {Array<Array<string|number>>} naturalsTable The Natural Contributions data (Name, Const, CAS, Perc).
 * @param {Array<Array<string|number>>} inventoryTable [Optional] The Inventory aliases (Stock Name, Mapped Name).
 * @param {Array<Array<string|number>>} userMatsTable [Optional] Custom materials (Name, Const, CAS, Perc).
 * @param {number} finishedDosage [Optional] The concentration percentage of compound in finished product (0-100%, defaults to 100%).
 * @return The compliance report table.
 * @customfunction
 */
function IFRA_COMPLIANCE_V5(formula, standardsTable, naturalsTable, inventoryTable, userMatsTable, finishedDosage) {

    // --- Hardcoded Phototoxic Oils List (Additivity Rule) ---
    // These specific oils must have their (Usage/Limit) summed up.
    // If Sum > 1.0 (100%), it fails.
    const PHOTOTOXIC_OILS = [
        "angelica root oil",
        "bergamot oil expressed",
        "bitter orange peel oil expressed", // Matches 'Bitter orange peel oil expressed' in DB
        "cumin oil",
        "grapefruit oil expressed",
        "lemon oil cold pressed",
        "lime oil expressed",
        "rue oil"
    ]; // Must be normalized (lowercase) for matching

    // 1. Parsing Helper: Normalize Strings
    const normalize = (str) => str ? str.toString().trim().toLowerCase() : "";

    // 1. Parse Databases (Arrays to Maps)
    const standards = parseStandards(standardsTable);
    const naturals = parseNaturals(naturalsTable);
    const inventory = inventoryTable ? parseInventory(inventoryTable) : {};
    const userMaterials = userMatsTable ? parseUserMaterials(userMatsTable) : {}; // Use new parser

    // 2. Calculate Exposure (CAS Level)
    const exposureMap = {};
    let totalFormulaAmount = 0;

    // Helper to process a material
    const processMaterial = (matName, amount) => {
        const normName = normalize(matName);

        // 1. Resolve Link/Alias
        // Check Inventory Map -> returns "Linked Name"
        const resolvedName = inventory[normName] || normName;
        const resolvedNorm = normalize(resolvedName);

        // 2. Check User Materials (Custom Bases) FIRST (Privacy Priority 1)
        if (userMaterials[resolvedNorm]) {
            for (let c of userMaterials[resolvedNorm]) {
                const c_amount = amount * (c.percentage / 100.0);
                addExposure(exposureMap, c.cas, c_amount, matName, "Indirect (Base)");
            }
        }
        // 3. Check Natural/Complex Contributions (Annex I) (Priority 2)
        else if (naturals[resolvedNorm]) {
            for (let c of naturals[resolvedNorm]) {
                const c_amount = amount * (c.percentage / 100.0);
                addExposure(exposureMap, c.cas, c_amount, matName, "Indirect (Natural)");
            }
        }
        // 4. Direct/Standard Material
        else {
            // Try matching resolved name first
            const stdParams = standards.find(s => s.normName === resolvedNorm);
            if (stdParams) {
                const cas = stdParams.cas[0];
                addExposure(exposureMap, cas, amount, matName, "Direct");
            }
        }
    };

    // Loop Formula Rows
    if (!Array.isArray(formula)) return [["Error: Formula must be a range"]];

    for (let row of formula) {
        const name = row[0];
        const amount = row[1];

        if (!name || amount === "" || amount == null) continue;
        const val = Number(amount);
        if (isNaN(val) || val <= 0) continue;

        totalFormulaAmount += val;
        processMaterial(name, val);
    }

    // 3. Group by Standard (Isomer Aggregation) & Prepare Phototoxicity Sum
    const groupedMap = {};
    let photoToxicSumRatio = 0.0;
    let photoToxicSources = [];

    for (let cas in exposureMap) {
        const entry = exposureMap[cas];
        if (entry.total <= 0) continue;

        const currentCas = cas.toString().trim();
        if (!currentCas) continue;

        const std = standards.find(s => s.cas.includes(currentCas));

        if (std) {
            const key = std.name;
            if (!groupedMap[key]) {
                groupedMap[key] = {
                    limit: std.limit,
                    total: 0,
                    sources: [],
                    casList: [],
                    normName: std.normName
                };
            }
            groupedMap[key].total += entry.total;
            groupedMap[key].casList.push(currentCas);
            groupedMap[key].sources.push(...entry.sources);
        }
    }

    // 4. Construct Output
    const details = [];
    const dosageVal = parseDosage(finishedDosage);

    for (let stdName in groupedMap) {
        if (totalFormulaAmount === 0) continue;

        const data = groupedMap[stdName];
        const rawConcentration = (data.total / totalFormulaAmount) * 100.0;
        const concentration = rawConcentration * (dosageVal / 100.0);
        const limit = data.limit;

        let status = "PASS";
        if (typeof limit === 'number') {
            if (concentration > limit) status = "FAIL";

            // --- PHOTOTOXICITY CHECK ---
            // If this ingredient is in the PHOTOTOXIC list, add to sum ratio.
            // Ratio = (Concentration % / Limit %)
            if (PHOTOTOXIC_OILS.includes(data.normName)) {
                photoToxicSumRatio += (concentration / limit);
                photoToxicSources.push(`${stdName} (${(concentration / limit * 100).toFixed(1)}% of limit)`);
            }
        }

        // Merge Sources
        const mergedSources = {};
        for (let src of data.sources) {
            const k = src.name + "||" + src.type;
            if (!mergedSources[k]) mergedSources[k] = { ...src, amount: 0 };
            mergedSources[k].amount += src.amount;
        }

        const sortedSources = Object.values(mergedSources).sort((a, b) => b.amount - a.amount);

        let sourceTextParts = [];
        for (let src of sortedSources) {
            if (src.amount <= 0) continue;
            const srcConc = (src.amount / totalFormulaAmount) * 100.0 * (dosageVal / 100.0);
            if (srcConc > 0.0001) {
                let label = src.name;
                if (src.type === "Direct") label = "Direct";
                sourceTextParts.push(`${label} (${srcConc.toFixed(4)}%)`);
            }
        }
        const sourceText = sourceTextParts.slice(0, 5).join(", ");
        const casText = [...new Set(data.casList)].join(", ");

        details.push({
            ingredient: stdName,
            cas: casText,
            conc: concentration,
            limit: limit,
            status: status,
            sources: sourceText
        });
    }

    // 5. Append Phototoxicity Aggregate Row
    if (photoToxicSources.length > 0) {
        const photoPercentage = photoToxicSumRatio * 100.0; // 1.0 = 100%
        let photoStatus = "PASS";
        if (photoPercentage > 100.0) photoStatus = "FAIL"; // Cannot exceed 100% of allowed ratio

        details.push({
            ingredient: "⚠️ Phototoxicity (Sum of Ratios)",
            cas: "Special",
            conc: photoPercentage,
            limit: 100, // Display as Limit=100% (Ratio=1.0)
            status: photoStatus,
            sources: photoToxicSources.join(", ")
        });
    }

    // 6. Final Table Construction
    const headers = ["Regulated Ingredient", "CAS", "Your Level (%)", "IFRA Limit (%)", "Status", "Contribution Sources"];
    const result = [headers];

    details.sort((a, b) => {
        if (a.status === "FAIL" && b.status !== "FAIL") return -1;
        if (a.status !== "FAIL" && b.status === "FAIL") return 1;

        // Put Phototoxicity row at top if fail, or high up
        if (a.ingredient.startsWith("⚠️") && a.status === "FAIL") return -1;

        return b.conc - a.conc;
    });

    if (details.length > 0) {
        for (let d of details) {
            result.push([
                d.ingredient,
                d.cas,
                Number(d.conc.toFixed(4)),
                d.limit,
                d.status,
                d.sources
            ]);
        }
        const failCount = details.filter(d => d.status === "FAIL").length;
        if (failCount === 0) {
            result.push(["✅ FINAL RESULT: ALL PASS (Dosage: " + dosageVal + "%)", "", "", "", "", ""]);
        } else {
            result.push(["❌ FINAL RESULT: " + failCount + " FAILS (Dosage: " + dosageVal + "%)", "", "", "", "", ""]);
        }
    } else {
        result.push(["No Regulated Ingredients Found", "-", "-", "-", "PASS", "-"]);
    }

    return result;
}

// --- Helpers ---

function parseDosage(finishedDosage) {
    if (finishedDosage === undefined || finishedDosage === null || finishedDosage === "") {
        return 100.0;
    }
    let val = finishedDosage;
    if (Array.isArray(val)) {
        if (val.length > 0 && Array.isArray(val[0])) {
            val = val[0][0];
        } else if (val.length > 0) {
            val = val[0];
        }
    }
    if (val === undefined || val === null || val === "") {
        return 100.0;
    }
    if (typeof val === 'string') {
        val = val.replace("%", "").trim();
    }
    const num = Number(val);
    return (isNaN(num) || num <= 0) ? 100.0 : num;
}

function addExposure(map, cas, amount, sourceName, type) {
    if (!cas) return;
    const strCas = cas.toString().trim();
    if (!map[strCas]) {
        map[strCas] = { total: 0, sources: [] };
    }
    map[strCas].total += amount;

    let existingSrc = map[strCas].sources.find(s => s.name === sourceName && s.type === type);
    if (existingSrc) {
        existingSrc.amount += amount;
    } else {
        map[strCas].sources.push({
            name: sourceName,
            amount: amount,
            type: type
        });
    }
}

function parseStandards(data) {
    if (!data) return [];
    const list = [];
    for (let row of data) {
        if (!row[0]) continue;
        const limit = Number(row[2]);
        if (isNaN(limit)) continue;

        list.push({
            name: row[0].toString(),
            normName: row[0].toString().trim().toLowerCase(),
            cas: row[1] ? row[1].toString().split("|") : [],
            limit: limit
        });
    }
    return list;
}

function parseNaturals(data) {
    if (!data) return {};
    const map = {};
    for (let row of data) {
        // DB_Naturals Format: [Name, Constituent, CAS, Percentage]
        const nat = row[0];
        if (!nat) continue;
        const pct = Number(row[3]);
        if (isNaN(pct)) continue;

        const natStr = nat.toString().trim().toLowerCase();
        if (!map[natStr]) map[natStr] = [];

        map[natStr].push({
            chemical: row[1],
            cas: row[2] ? row[2].toString() : "",
            percentage: pct
        });
    }
    return map;
}

function parseUserMaterials(data) {
    if (!data) return {};
    const map = {};
    for (let row of data) {
        if (!row || row.length < 2) continue;
        
        let matName = "";
        let chemical = "";
        let cas = "";
        let pctVal = "";
        
        // Detect layout dynamically
        if (row.length >= 5 && isNaN(Number(row[0])) && !isNaN(Number(row[4]))) {
            // 5-Column Format: SKU, Material Name, Constituent, CAS, Percentage
            matName = row[1];
            chemical = row[2];
            cas = row[3];
            pctVal = row[4];
        } else if (row.length >= 4 && !isNaN(Number(row[3]))) {
            // 4-Column Format: Material Name, Constituent, CAS, Percentage
            matName = row[0];
            chemical = row[1];
            cas = row[2];
            pctVal = row[3];
        } else {
            // Fallback: search for percentage column (last numeric column)
            let pctIdx = -1;
            for (let i = row.length - 1; i >= 0; i--) {
                if (row[i] !== "" && !isNaN(Number(row[i]))) {
                    pctIdx = i;
                    break;
                }
            }
            if (pctIdx >= 3) {
                matName = row[1];
                chemical = row[2];
                cas = row[pctIdx - 1];
                pctVal = row[pctIdx];
            } else if (pctIdx >= 2) {
                matName = row[0];
                chemical = row[1];
                cas = row[pctIdx - 1];
                pctVal = row[pctIdx];
            } else {
                continue; // Cannot parse
            }
        }
        
        if (!matName) continue;
        if (pctVal === undefined || pctVal === "") continue;
        const pct = Number(pctVal);
        if (isNaN(pct)) continue;
        
        const normKey = matName.toString().trim().toLowerCase();
        if (!map[normKey]) map[normKey] = [];
        
        map[normKey].push({
            chemical: chemical ? chemical.toString() : "",
            cas: cas ? cas.toString().trim() : "",
            percentage: pct
        });
    }
    return map;
}

function parseInventory(data) {
    if (!data) return {};
    const map = {};
    for (let row of data) {
        if (row.length >= 4) {
            const stockName = row[2];
            const linkedName = row[3];
            if (stockName && linkedName) {
                map[stockName.toString().trim().toLowerCase()] = linkedName.toString().trim();
            }
        } else if (row.length >= 2) {
            const stockName = row[0];
            const linkedName = row[1];
            if (stockName && linkedName) {
                map[stockName.toString().trim().toLowerCase()] = linkedName.toString().trim();
            }
        }
    }
    return map;
}

/**
 * Checks EU 2023/1545 Allergen Labeling requirements for a fragrance formula.
 * 
 * Usage:
 * =EU_LABELING_V5(FormulaRange, AllergensRange, NaturalsRange, InventoryRange, UserMaterialsRange, ProductType, FinishedDosage)
 * 
 * Example:
 * =EU_LABELING_V5(A2:B, DB_EU_Allergens!A2:B, DB_Naturals!A2:D, DB_Inventory!A2:B, DB_User_Materials!A2:E, "Leave-on", 20)
 * 
 * @param {Array<Array<string|number>>} formula The formula range (Name, Amount).
 * @param {Array<Array<string|number>>} allergensTable The EU Allergens data (INCI Name, CAS).
 * @param {Array<Array<string|number>>} naturalsTable The Natural Contributions data (Name, Const, CAS, Perc).
 * @param {Array<Array<string|number>>} inventoryTable [Optional] The Inventory aliases (Stock Name, Mapped Name).
 * @param {Array<Array<string|number>>} userMatsTable [Optional] Custom materials (Name, Const, CAS, Perc).
 * @param {string} productType [Optional] "Leave-on" (default, 0.001% threshold) or "Rinse-off" (0.01% threshold).
 * @param {number} finishedDosage [Optional] The concentration percentage of compound in finished product (0-100%, defaults to 100%).
 * @return The EU Allergen Labeling report table.
 * @customfunction
 */
function EU_LABELING_V5(formula, allergensTable, naturalsTable, inventoryTable, userMatsTable, productType, finishedDosage) {
    const normalize = (str) => str ? str.toString().trim().toLowerCase() : "";
    const typeStr = normalize(productType) === "rinse-off" ? "rinse-off" : "leave-on";
    const threshold = typeStr === "rinse-off" ? 0.01 : 0.001;
    const dosageVal = parseDosage(finishedDosage);

    // Parse Databases
    const allergens = parseAllergens(allergensTable);
    const naturals = parseNaturals(naturalsTable);
    const inventory = inventoryTable ? parseInventory(inventoryTable) : {};
    const userMaterials = userMatsTable ? parseUserMaterials(userMatsTable) : {};

    // Calculate Exposure
    const exposureMap = {};
    let totalFormulaAmount = 0;

    const processMaterial = (matName, amount) => {
        const normName = normalize(matName);
        const resolvedName = inventory[normName] || normName;
        const resolvedNorm = normalize(resolvedName);

        if (userMaterials[resolvedNorm]) {
            for (let c of userMaterials[resolvedNorm]) {
                const c_amount = amount * (c.percentage / 100.0);
                addExposure(exposureMap, c.cas, c_amount, matName, "Indirect (Base)");
            }
        } else if (naturals[resolvedNorm]) {
            for (let c of naturals[resolvedNorm]) {
                const c_amount = amount * (c.percentage / 100.0);
                addExposure(exposureMap, c.cas, c_amount, matName, "Indirect (Natural)");
            }
        } else {
            const cleanName = matName.toString().trim();
            if (/^\d+-\d+-\d+$/.test(cleanName)) {
                addExposure(exposureMap, cleanName, amount, matName, "Direct");
            } else {
                const matchedAllergen = allergens.find(a => a.normName === resolvedNorm);
                if (matchedAllergen && matchedAllergen.casList.length > 0) {
                    addExposure(exposureMap, matchedAllergen.casList[0], amount, matName, "Direct");
                }
            }
        }
    };

    // Loop Formula Rows
    if (!Array.isArray(formula)) return [["Error: Formula must be a range"]];

    for (let row of formula) {
        const name = row[0];
        const amount = row[1];

        if (!name || amount === "" || amount == null) continue;
        const val = Number(amount);
        if (isNaN(val) || val <= 0) continue;

        totalFormulaAmount += val;
        processMaterial(name, val);
    }

    const details = [];
    const requiredLabels = [];

    // Loop through reference allergens
    for (let allergen of allergens) {
        if (allergen.casList.length === 0) continue;
        
        let allergenTotalExposure = 0.0;
        const matchedSources = [];

        // Sum up exposure from all isomeric CAS numbers
        for (let cas_key of allergen.casList) {
            if (exposureMap[cas_key]) {
                allergenTotalExposure += exposureMap[cas_key].total;
                matchedSources.push(...exposureMap[cas_key].sources);
            }
        }

        if (allergenTotalExposure > 0 && totalFormulaAmount > 0) {
            const rawConcPct = (allergenTotalExposure / totalFormulaAmount) * 100.0;
            const finalConcPct = rawConcPct * (dosageVal / 100.0);
            const thresholdPct = threshold * 100.0;
            const required = finalConcPct > thresholdPct;

            if (required) {
                requiredLabels.push(allergen.name);
            }

            // Merge sources
            const mergedSources = {};
            for (let src of matchedSources) {
                const k = src.name + "||" + src.type;
                if (!mergedSources[k]) mergedSources[k] = { ...src, amount: 0 };
                mergedSources[k].amount += src.amount;
            }
            const sortedSources = Object.values(mergedSources).sort((a, b) => b.amount - a.amount);
            const sourceTextParts = [];
            for (let src of sortedSources) {
                if (src.amount <= 0) continue;
                const srcConc = (src.amount / totalFormulaAmount) * 100.0 * (dosageVal / 100.0);
                if (srcConc > 0.0001) {
                    let label = src.name;
                    if (src.type === "Direct") label = "Direct";
                    sourceTextParts.push(`${label} (${srcConc.toFixed(4)}%)`);
                }
            }

            details.push({
                name: allergen.name,
                cas: allergen.casList.join(", "),
                conc: finalConcPct,
                threshold: thresholdPct,
                required: required ? "REQUIRED" : "NO",
                sources: sourceTextParts.slice(0, 5).join(", ")
            });
        }
    }

    // Build Table
    const headers = ["Allergen Name", "CAS References", "Concentration (%)", "Threshold (%)", "Required on Label", "Contribution Sources"];
    const result = [headers];

    details.sort((a, b) => {
        if (a.required === "REQUIRED" && b.required !== "REQUIRED") return -1;
        if (a.required !== "REQUIRED" && b.required === "REQUIRED") return 1;
        return b.conc - a.conc;
    });

    for (let d of details) {
        result.push([
            d.name,
            d.cas,
            Number(d.conc.toFixed(4)),
            Number(d.threshold.toFixed(4)),
            d.required,
            d.sources
        ]);
    }

    if (requiredLabels.length > 0) {
        result.push([`Required Labels: ${requiredLabels.join(", ")} (Dosage: ${dosageVal}%)`, "", "", "", "", ""]);
    } else {
        result.push([`No allergens exceed threshold (Dosage: ${dosageVal}%)`, "", "", "", "", ""]);
    }

    return result;
}

function parseAllergens(data) {
    if (!data) return [];
    const list = [];
    for (let row of data) {
        if (!row[0]) continue;
        list.push({
            name: row[0].toString().trim(),
            normName: row[0].toString().trim().toLowerCase(),
            casList: row[1] ? row[1].toString().split("|").map(c => c.trim().toLowerCase()) : []
        });
    }
    return list;
}
