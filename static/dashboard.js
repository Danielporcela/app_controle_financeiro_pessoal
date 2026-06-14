document.addEventListener("DOMContentLoaded", function () {

    const canvas = document.getElementById("grafico");

    if (!canvas) {
        return;
    }

    const receitas = parseFloat(
        canvas.dataset.receitas || 0
    );

    const despesas = parseFloat(
        canvas.dataset.despesas || 0
    );

    const saldo = parseFloat(
        canvas.dataset.saldo || 0
    );

    new Chart(canvas, {

        type: "bar",

        data: {

            labels: [
                "Receitas",
                "Despesas",
                "Saldo"
            ],

            datasets: [{
                label: "Resumo Financeiro",

                data: [
                    receitas,
                    despesas,
                    saldo
                ],

                backgroundColor: [
                    "#22C55E",
                    "#EF4444",
                    "#3B82F6"
                ],

                borderWidth: 1
            }]
        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            plugins: {

                legend: {
                    display: true
                }

            },

            scales: {

                y: {

                    beginAtZero: true

                }

            }

        }

    });

});