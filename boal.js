// BOAL Interpreter v1 (Patched)
// Improved parsing, flexible syntax, safer execution

function runBOAL(code) {
    try {
        const ast = parseBOAL(code);
        return executeBOAL(ast);
    } catch (err) {
        console.error("BOAL Error:", err.message);
        return null;
    }
}

// ---------------- LEXER + PARSER ----------------
function parseBOAL(code) {
    const lines = code
        .split("\n")
        .map(l => l.trim())
        .filter(l => l.length > 0 && !l.startsWith("//"));

    let ast = {
        ce: null,
        attr: {},
        ci: [],
        verify: null
    };

    let currentCI = null;

    for (let raw of lines) {
        // normalize line (remove trailing semicolons and braces spacing)
        let line = raw.replace(/;$/, "").trim();

        // Skip block braces
        if (line === "{" ) continue;
        if (line === "}") {
            currentCI = null;
            continue;
        }

        // CE block (e.g., ce main {)
        if (line.startsWith("ce ")) {
            const parts = line.split(/\s+/);
            ast.ce = parts[1];
            continue;
        }

        // ATTR (flexible: attr a=valid; | attr a = valid | attr a = true)
        if (line.startsWith("attr ")) {
            const cleaned = line.replace(/;$/, "");
            // split on = first
            const [left, right] = cleaned.split("=");
            if (!right) continue;
            const key = left.replace("attr", "").trim().split(/\s+/)[0];
            let value = right.trim().toLowerCase();
            // normalize booleans
            const truthy = ["valid", "verified", "true", "1", "yes"];
            ast.attr[key] = truthy.includes(value);
            continue;
        }

        // CI start (e.g., ci process {)
        if (line.startsWith("ci ")) {
            const parts = line.split(/\s+/);
            currentCI = {
                name: parts[1],
                body: []
            };
            ast.ci.push(currentCI);
            continue;
        }

        // inside CI (key = value)
        if (currentCI && line.includes("=")) {
            const [k, v] = line.split("=");
            let key = k.trim();
            let value = (v || "").trim();

            // strip quotes
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
                value = value.slice(1, -1);
            }

            currentCI.body.push({ key, value });
            continue;
        }

        // VERIFY (flexible spacing)
        if (line.startsWith("verify ")) {
            ast.verify = line.replace("verify", "").trim();
            continue;
        }
    }

    return ast;
}

// ---------------- EXECUTOR ----------------
function executeBOAL(ast) {

    // CE validation
    if (!ast.ce) {
        throw new Error("Missing CE block");
    }

    // ATTR validation (must have at least one true)
    const attrValues = Object.values(ast.attr);
    const attrValid = attrValues.length > 0 && attrValues.some(v => v === true);

    if (!attrValid) {
        console.warn("BOAL: Attribution failed → NULL state");
        return null; // BO42 null-state
    }

    let ciResults = {};

    // Execute CI blocks
    for (let ci of ast.ci) {
        let result = {};

        for (let stmt of ci.body) {
            result[stmt.key] = stmt.value;
        }

        ciResults[ci.name] = result;
    }

    // VERIFY logic (basic patterns)
    if (ast.verify) {
        const v = ast.verify.replace(/;$/, "");

        // pattern: <attr> -> out
        if (/->\s*out/.test(v)) {
            const firstCI = Object.values(ciResults)[0];
            if (firstCI && typeof firstCI.out !== "undefined") {
                return firstCI.out;
            }
        }

        // pattern: <attr> && (forward == reverse) -> out (simple equality check)
        if (/==/.test(v) && /->\s*out/.test(v)) {
            // naive equality check between first two CI blocks if present
            const cis = Object.values(ciResults);
            if (cis.length >= 2) {
                const a = JSON.stringify(cis[0]);
                const b = JSON.stringify(cis[1]);
                if (a === b) {
                    const out = cis[0].out ?? cis[1].out;
                    if (typeof out !== "undefined") return out;
                }
            }
        }
    }

    return ciResults;
}

// ---------------- TEST ----------------
const sample = `
ce main {

    attr auth = valid;

    ci process {
        out = "Halleluyah BO42 is Alive!";
    }

    verify auth -> out;

}
`;

console.log("BOAL Output:", runBOAL(sample));

// ---------------- EXPORT (for browser) ----------------
if (typeof window !== "undefined") {
    window.runBOAL = runBOAL;
}