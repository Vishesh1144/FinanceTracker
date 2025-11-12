
    const expenseCategories = ["Food", "Travel", "Shopping", "Bills", "Health", "Entertainment", "Other"];
    const incomeCategories = ["Salary", "Freelance", "Investments", "Business", "Other"];

    const typeSelect = document.getElementById("expenseType");
    const categorySelect = document.getElementById("expenseCategory");

    function updateCategories() {
        const selectedType = typeSelect.value;
        let options = [];

        if (selectedType === "Expense") {
            options = expenseCategories;
        } else if (selectedType === "Income") {
            options = incomeCategories;
        }

        categorySelect.innerHTML = options.map(c => `<option value="${c}">${c}</option>`).join("");
    }

    typeSelect.addEventListener("change", updateCategories);

    // initialize on page load
    updateCategories();
