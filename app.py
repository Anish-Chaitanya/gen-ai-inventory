from flask import Flask, request, render_template, send_file, jsonify
import pandas as pd
import os
# Folder setup
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

input_file_path = None
output_file_path = os.path.join(UPLOAD_FOLDER, "processed_inventory.xlsx")

# ====================
# Excel Processor
# ====================
def process_excel(file_path):
    df = pd.read_excel(file_path)

    required_columns = {"Product Name", "Expiry Date", "Bought Date", "Current Date", "Total Quantity", "Sold Quantity", "Product Price"}
    if not required_columns.issubset(df.columns):
        return None, "Missing required columns in Excel file."

    df["Expiry Date"] = pd.to_datetime(df["Expiry Date"])
    df["Bought Date"] = pd.to_datetime(df["Bought Date"])
    df["Current Date"] = pd.to_datetime(df["Current Date"])

    # Markup ≤ 20%
    df["Sold Price"] = df["Product Price"] * (1 + df["Product Price"].apply(lambda x: min(0.2, x * 0.01)))
    df["Sold Price"] = df["Sold Price"].round(2)

    df["Sold Percentage"] = (df["Sold Quantity"] / df["Total Quantity"]) * 100

    def calculate_reorder(row):
        if row["Sold Percentage"] < 25:
            return row["Total Quantity"] - (row["Total Quantity"] * 0.3)
        elif 25 <= row["Sold Percentage"] <= 75:
            return row["Total Quantity"]
        else:
            return row["Total Quantity"] + (row["Total Quantity"] * 0.3)

    df["Reorder Quantity"] = df.apply(calculate_reorder, axis=1)

    def calculate_discount(row):
        days_to_expiry = (row["Expiry Date"] - row["Current Date"]).days
        if days_to_expiry > 10:
            return "No Discount"
        elif 5 < days_to_expiry <= 10:
            return "10% Discount"
        elif 2 < days_to_expiry <= 5:
            return "20% Discount"
        else:
            return "50% Discount"

    df["Discount"] = df.apply(calculate_discount, axis=1)

    df.to_excel(output_file_path, index=False)
    return df, None

# ====================
# ROUTES
# ====================

# Admin view (password protected)
@app.route('/')
@auth.login_required
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global input_file_path
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    input_file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_file_path)

    processed_df, error = process_excel(input_file_path)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"message": "File processed successfully"})

@app.route('/input-data')
@auth.login_required
def input_data():
    if input_file_path is None:
        return "<p>No file uploaded yet.</p>"
    df = pd.read_excel(input_file_path)
    return df.to_html(classes='table table-striped', index=False)

@app.route('/output-data')
@auth.login_required
def output_data():
    if not os.path.exists(output_file_path):
        return "<p>No processed data available yet.</p>"
    df = pd.read_excel(output_file_path)
    return df.to_html(classes='table table-striped', index=False)

@app.route('/download')
@auth.login_required
def download_file():
    return send_file(output_file_path, as_attachment=True)

# ====================
# Customer View
# ====================
@app.route('/customer')
def customer_view():
    if not os.path.exists(output_file_path):
        return "<p>No processed inventory available yet.</p>"

    df = pd.read_excel(output_file_path)
    product_labels = (df["Product Name"] + " ₹" + df["Sold Price"].round(2).astype(str)).tolist()
    sold_quantities = df["Sold Quantity"].tolist()

    return render_template(
        'customer.html',
        table=df.to_html(classes='table table-striped', index=False),
        product_labels=product_labels,
        sold_quantities=sold_quantities
    )
# ====================
# Run
# ====================
if __name__ == '__main__':
    app.run(debug=True)
