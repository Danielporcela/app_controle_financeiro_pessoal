from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta


app = Flask(__name__)


DB = "financeiro.db"


def conn():
    return sqlite3.connect(DB)


def criar_tabelas():

    con = conn()
    con.execute("""
CREATE TABLE IF NOT EXISTS despesas_fixas(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    categoria TEXT,
    valor REAL,
    vencimento INTEGER,
    recorrente INTEGER DEFAULT 1
)
""")

    con.execute("""
CREATE TABLE IF NOT EXISTS compras_cartao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cartao_id INTEGER,
    descricao TEXT,
    valor REAL,
    parcelas INTEGER,
    data_compra TEXT,
    FOREIGN KEY(cartao_id) REFERENCES cartoes(id)
)
""")

    con.execute("""
    CREATE TABLE IF NOT EXISTS receitas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS parcelas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    parcela INTEGER NOT NULL,
    total_parcelas INTEGER NOT NULL,
    vencimento TEXT NOT NULL,
    compra_cartao_id INTEGER
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS metas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        objetivo REAL NOT NULL,
        atual REAL DEFAULT 0
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS cartoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        limite REAL NOT NULL,
        utilizado REAL DEFAULT 0
    )
    """)

    con.commit()
    con.close()


@app.route("/")
def dashboard():

    con = conn()

    receitas = con.execute("SELECT COALESCE(SUM(valor),0) FROM receitas").fetchone()[0]

    mes_atual = datetime.now().strftime("%Y-%m")

    despesas_cartao = con.execute(
        """
    SELECT COALESCE(SUM(valor),0)
    FROM parcelas
    WHERE strftime('%Y-%m', vencimento)=?
""",
        (mes_atual,),
    ).fetchone()[0]

    compras_mes_cartao = con.execute("""
    SELECT COALESCE(SUM(valor),0)
    FROM compras_cartao
    WHERE strftime('%Y-%m', data_compra)=?
""", (mes_atual,)).fetchone()[0]

    despesas_fixas = con.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM despesas_fixas
    """).fetchone()[0]

    despesas = despesas_cartao + despesas_fixas

    total_metas = con.execute("SELECT COUNT(*) FROM metas").fetchone()[0]

    total_cartoes = con.execute("SELECT COUNT(*) FROM cartoes").fetchone()[0]

    saldo = receitas - despesas

    percentual_gasto = 0

    if receitas > 0:
        percentual_gasto = (despesas / receitas) * 100

    score = 100

    if percentual_gasto >= 100:
        score -= 50

    elif percentual_gasto >= 90:
        score -= 40

    elif percentual_gasto >= 80:
        score -= 30

    elif percentual_gasto >= 70:
        score -= 20

    elif percentual_gasto >= 60:
        score -= 10

    if total_metas == 0:
        score -= 10

    if saldo < 0:
        score -= 20

    if score < 0:
        score = 0

    if score >= 90:
        classificacao = "🟢 Excelente"

    elif score >= 70:
        classificacao = "🟡 Bom"

    elif score >= 50:
        classificacao = "🟠 Atenção"

    else:
        classificacao = "🔴 Crítico"

    con.close()
    return render_template(
        "dashboard.html",
        receitas=receitas,
        despesas=despesas,
        saldo=saldo,
        metas=total_metas,
        cartoes=total_cartoes,
        score=score,
        classificacao=classificacao,
        percentual_gasto=percentual_gasto,
        compras_mes_cartao=compras_mes_cartao,
    )


@app.route("/despesas")
def despesas_lista():

    mes = request.args.get(
        "mes",
        datetime.now().strftime("%Y-%m")
    )

    con = conn()

    despesas = con.execute("""
        SELECT
            id,
            descricao,
            valor,
            parcela,
            total_parcelas,
            vencimento
        FROM parcelas
        WHERE strftime('%Y-%m', vencimento)=?
        ORDER BY vencimento
    """, (mes,)).fetchall()

    con.close()

    return render_template(
        "despesas.html",
        despesas=despesas,
        mes=mes
    )


@app.route("/metas")
def metas_lista():

    con = conn()

    metas = con.execute("""
        SELECT *
        FROM metas
        ORDER BY id DESC
    """).fetchall()

    metas_previsao = []

    for meta in metas:

        restante = meta[2] - meta[3]

        meses = round(restante / 500) if restante > 0 else 0

        metas_previsao.append(meses)

    con.close()

    return render_template(
        "metas.html",
        metas=metas,
        metas_previsao=metas_previsao
    )


@app.route("/cartoes")
def cartoes_lista():

    con = conn()

    cartoes_db = con.execute("""
        SELECT *
        FROM cartoes
        ORDER BY id DESC
    """).fetchall()

    mes_atual = datetime.now().strftime("%Y-%m")

    cartoes = []

    alertas = []

    for c in cartoes_db:

        limite = c[2]
        utilizado = c[3]

        disponivel = limite - utilizado

        fatura_atual = con.execute(
            """
            SELECT COALESCE(SUM(parcelas.valor),0)
            FROM parcelas
            INNER JOIN compras_cartao
                ON compras_cartao.id =
                   parcelas.compra_cartao_id
            WHERE compras_cartao.cartao_id = ?
            AND strftime('%Y-%m', parcelas.vencimento)=?
        """,
            (c[0], mes_atual),
        ).fetchone()[0]

        percentual = 0

        if limite > 0:

            percentual = (utilizado / limite) * 100

            if percentual >= 80:

                alertas.append(f"{c[1]} está usando {percentual:.1f}% do limite")

        cartoes.append(
            {
                "id": c[0],
                "nome": c[1],
                "limite": limite,
                "utilizado": utilizado,
                "disponivel": disponivel,
                "percentual": percentual,
                "fatura": fatura_atual,
            }
        )

    con.close()

    return render_template("cartoes.html", cartoes=cartoes, alertas=alertas)


@app.route("/receita", methods=["POST"])
def receita():

    descricao = request.form["descricao"]
    valor = float(request.form["valor"])

    con = conn()

    con.execute("""
        INSERT INTO receitas (
            descricao,
            valor,
            data
        )
        VALUES (?, ?, ?)
    """, (
        descricao,
        valor,
        datetime.now().strftime("%Y-%m-%d")
    ))

    con.commit()
    con.close()

    return redirect("/receitas")


@app.route("/despesa", methods=["POST"])
def despesa():

    descricao = request.form["descricao"]
    valor = float(request.form["valor"])
    parcelas = int(request.form["parcelas"])

    con = conn()

    valor_parcela = round(valor / parcelas, 2)

    for i in range(parcelas):

        vencimento = datetime.now() + relativedelta(months=i)

        con.execute("""
            INSERT INTO parcelas (
                descricao,
                valor,
                parcela,
                total_parcelas,
                vencimento
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            descricao,
            valor_parcela,
            i + 1,
            parcelas,
            vencimento.strftime("%Y-%m-%d")
        ))

    con.execute("""
        INSERT INTO despesas (
            descricao,
            valor,
            data
        )
        VALUES (?, ?, ?)
    """, (
        descricao,
        valor,
        datetime.now().strftime("%Y-%m-%d")
    ))

    con.commit()
    con.close()

    return redirect("/despesas")


@app.route("/excluir_receita/<int:id>")
def excluir_receita(id):

    con = conn()

    con.execute(
        "DELETE FROM receitas WHERE id=?",
        (id,)
    )

    con.commit()
    con.close()

    return redirect("/receitas")


@app.route("/excluir_despesa/<int:id>")
def excluir_despesa(id):

    con = conn()

    despesa = con.execute(
        "SELECT descricao FROM despesas WHERE id=?",
        (id,)
    ).fetchone()

    if despesa:

        descricao = despesa[0]

        con.execute(
            "DELETE FROM parcelas WHERE descricao=?",
            (descricao,)
        )

        con.execute(
            "DELETE FROM despesas WHERE id=?",
            (id,)
        )

    con.commit()
    con.close()

    return redirect("/despesas")

@app.route("/excluir_parcela/<int:id>")
def excluir_parcela(id):

    con = conn()

    con.execute(
        "DELETE FROM parcelas WHERE id=?",
        (id,)
    )

    con.commit()
    con.close()

    return redirect("/despesas")

@app.route("/calendario")
def calendario():

    con = conn()

    eventos = con.execute("""
        SELECT
            id,
            descricao,
            vencimento,
            valor
        FROM parcelas
        ORDER BY vencimento
    """).fetchall()

    con.close()

    return render_template(
        "calendario.html",
        eventos=eventos
    )


@app.route("/meta", methods=["POST"])
def criar_meta():

    descricao = request.form["descricao"]
    objetivo = float(request.form["objetivo"])

    con = conn()

    con.execute("""
        INSERT INTO metas(
            descricao,
            objetivo,
            atual
        )
        VALUES(?,?,0)
    """, (
        descricao,
        objetivo
    ))

    con.commit()
    con.close()

    return redirect("/metas")


@app.route("/meta/adicionar/<int:id>", methods=["POST"])
def adicionar_meta(id):

    valor = float(
        request.form["valor"]
    )

    con = conn()

    con.execute("""
        UPDATE metas
        SET atual = atual + ?
        WHERE id = ?
    """, (
        valor,
        id
    ))

    con.commit()
    con.close()

    return redirect("/metas")


@app.route("/excluir_meta/<int:id>")
def excluir_meta(id):

    con = conn()

    con.execute(
        "DELETE FROM metas WHERE id=?",
        (id,)
    )

    con.commit()
    con.close()

    return redirect("/metas")

@app.route("/simular", methods=["POST"])
def simular():

    objetivo = float(
        request.form["objetivo"]
    )

    aporte = float(
        request.form["aporte"]
    )

    if aporte <= 0:

        return {
            "erro": "Aporte deve ser maior que zero"
        }

    meses = round(
        objetivo / aporte
    )

    return {
        "objetivo": objetivo,
        "aporte": aporte,
        "meses": meses
    }


@app.route("/cartao", methods=["POST"])
def criar_cartao():

    nome = request.form["nome"]
    limite = float(request.form["limite"])

    con = conn()

    con.execute("""
        INSERT INTO cartoes(
            nome,
            limite,
            utilizado
        )
        VALUES(?,?,0)
    """, (
        nome,
        limite
    ))

    con.commit()
    con.close()

    return redirect("/cartoes")

@app.route("/compras_cartao")
def compras_cartao():

    con = conn()

    cartoes = con.execute("""
        SELECT *
        FROM cartoes
        ORDER BY nome
    """).fetchall()

    compras = con.execute("""
        SELECT
            compras_cartao.id,
            cartoes.nome,
            compras_cartao.descricao,
            compras_cartao.valor,
            compras_cartao.parcelas,
            compras_cartao.data_compra
        FROM compras_cartao
        INNER JOIN cartoes
            ON cartoes.id = compras_cartao.cartao_id
        ORDER BY compras_cartao.id DESC
    """).fetchall()

    con.close()

    return render_template(
        "compras_cartao.html",
        cartoes=cartoes,
        compras=compras
    )


@app.route("/compra_cartao", methods=["POST"])
def compra_cartao():

    cartao_id = int(request.form["cartao_id"])
    descricao = request.form["descricao"]
    valor = float(request.form["valor"])
    parcelas = int(request.form["parcelas"])

    con = conn()

    con.execute(
        """
        INSERT INTO compras_cartao(
            cartao_id,
            descricao,
            valor,
            parcelas,
            data_compra
        )
        VALUES(?,?,?,?,?)
    """,
        (cartao_id, descricao, valor, parcelas, datetime.now().strftime("%Y-%m-%d")),
    )

    compra_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

    con.execute(
        """
        UPDATE cartoes
        SET utilizado = utilizado + ?
        WHERE id = ?
    """,
        (valor, cartao_id),
    )

    valor_parcela = round(valor / parcelas, 2)

    for i in range(parcelas):

        vencimento = datetime.now() + relativedelta(months=i)

        con.execute(
            """
            INSERT INTO parcelas(
                descricao,
                valor,
                parcela,
                total_parcelas,
                vencimento,
                compra_cartao_id
            )
            VALUES(?,?,?,?,?,?)
        """,
            (
                f"[Cartão] {descricao}",
                valor_parcela,
                i + 1,
                parcelas,
                vencimento.strftime("%Y-%m-%d"),
                compra_id,
            ),
        )

    con.commit()
    con.close()

    return redirect("/compras_cartao")


@app.route("/excluir_compra_cartao/<int:id>")
def excluir_compra_cartao(id):

    con = conn()

    compra = con.execute("""
        SELECT
            cartao_id,
            valor,
            descricao
        FROM compras_cartao
        WHERE id=?
    """, (id,)).fetchone()

    if compra:

        cartao_id = compra[0]
        valor = compra[1]

        con.execute("""
            UPDATE cartoes
            SET utilizado = utilizado - ?
            WHERE id = ?
        """, (
            valor,
            cartao_id
        ))

        con.execute(
            """
           DELETE FROM parcelas
           WHERE compra_cartao_id = ?
        """,
            (id,),
        )

        con.execute("""
            DELETE FROM compras_cartao
            WHERE id = ?
        """, (id,))

    con.commit()
    con.close()

    return redirect("/compras_cartao")


@app.route("/despesas_fixas")
def despesas_fixas():

    con = conn()

    despesas = con.execute("""
        SELECT *
        FROM despesas_fixas
        ORDER BY id DESC
    """).fetchall()

    con.close()

    return render_template("despesas_fixas.html", despesas=despesas)


@app.route("/despesa_fixa", methods=["POST"])
def despesa_fixa():

    descricao = request.form["descricao"]
    categoria = request.form["categoria"]
    valor = float(request.form["valor"])
    vencimento = int(request.form["vencimento"])

    con = conn()

    con.execute(
        """
        INSERT INTO despesas_fixas(
            descricao,
            categoria,
            valor,
            vencimento
        )
        VALUES(?,?,?,?)
    """,
        (descricao, categoria, valor, vencimento),
    )

    con.commit()
    con.close()

    return redirect("/despesas_fixas")


@app.route("/receitas")
def receitas_lista():

    con = conn()

    receitas = con.execute("""
        SELECT *
        FROM receitas
        ORDER BY id DESC
    """).fetchall()

    con.close()

    return render_template("receitas.html", receitas=receitas)


@app.route("/fatura/<int:cartao_id>")
def fatura_cartao(cartao_id):

    mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))

    con = conn()

    cartao = con.execute(
        """
        SELECT *
        FROM cartoes
        WHERE id = ?
    """,
        (cartao_id,),
    ).fetchone()

    fatura = con.execute(
        """
        SELECT
            COALESCE(SUM(parcelas.valor),0)
        FROM parcelas
        INNER JOIN compras_cartao
            ON compras_cartao.id =
               parcelas.compra_cartao_id
        WHERE compras_cartao.cartao_id = ?
        AND strftime('%Y-%m', parcelas.vencimento)=?
    """,
        (cartao_id, mes),
    ).fetchone()[0]

    compras = con.execute(
        """
        SELECT
            parcelas.descricao,
            parcelas.valor,
            parcelas.parcela,
            parcelas.total_parcelas,
            parcelas.vencimento
        FROM parcelas
        INNER JOIN compras_cartao
            ON compras_cartao.id =
               parcelas.compra_cartao_id
        WHERE compras_cartao.cartao_id = ?
        AND strftime('%Y-%m', parcelas.vencimento)=?
        ORDER BY parcelas.vencimento
    """,
        (cartao_id, mes),
    ).fetchall()

    con.close()

    return render_template(
        "fatura.html", cartao=cartao, compras=compras, fatura=fatura, mes=mes
    )


@app.route("/planejamento")
def planejamento():

    con = conn()

    gastos_mes = []

    parcelas_db = con.execute("""
        SELECT
            valor,
            vencimento
        FROM parcelas
    """).fetchall()

    parcelas_mes = {}

    for valor, vencimento in parcelas_db:

        data = datetime.strptime(vencimento, "%Y-%m-%d")

        # joga para o mês seguinte
        data = data + relativedelta(months=1)

        mes = data.strftime("%Y-%m")

        parcelas_mes[mes] = parcelas_mes.get(mes, 0) + valor

    parcelas_mes = sorted(parcelas_mes.items())

    despesas_fixas_total = con.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM despesas_fixas
    """).fetchone()[0]

    for item in parcelas_mes:

        total_mes = item[1] + despesas_fixas_total

        gastos_mes.append((item[0], total_mes))

    metas = con.execute("""
        SELECT *
        FROM metas
    """).fetchall()

    cartoes = con.execute("""
        SELECT *
        FROM cartoes
    """).fetchall()

    projecao_12m = gastos_mes

    mes_atual = datetime.now().strftime("%Y-%m")

    receitas_total = con.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM receitas
    """).fetchone()[0]

    despesas_cartao = con.execute(
        """
        SELECT COALESCE(SUM(valor),0)
        FROM parcelas
        WHERE strftime('%Y-%m', vencimento)=?
    """,
        (mes_atual,),
    ).fetchone()[0]

    despesas_fixas = con.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM despesas_fixas
    """).fetchone()[0]

    despesas_total = despesas_cartao + despesas_fixas

    saldo_previsto = receitas_total - despesas_total

    percentual_comprometido = 0

    if receitas_total > 0:
        percentual_comprometido = (despesas_total / receitas_total) * 100

    con.close()

    return render_template(
        "planejamento.html",
        gastos_mes=gastos_mes,
        metas=metas,
        cartoes=cartoes,
        saldo_previsto=saldo_previsto,
        projecao_12m=projecao_12m,
        percentual_comprometido=percentual_comprometido,
    )


@app.route("/aumentar_limite/<int:id>", methods=["POST"])
def aumentar_limite(id):

    valor = float(request.form["valor"])

    con = conn()

    con.execute(
        """
        UPDATE cartoes
        SET limite = limite + ?
        WHERE id = ?
    """,
        (valor, id),
    )

    con.commit()
    con.close()

    return redirect("/cartoes")


@app.route("/excluir_despesa_fixa/<int:id>")
def excluir_despesa_fixa(id):

    con = conn()

    con.execute("DELETE FROM despesas_fixas WHERE id=?", (id,))

    con.commit()
    con.close()

    return redirect("/despesas_fixas")


if __name__ == "__main__":

    criar_tabelas()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
