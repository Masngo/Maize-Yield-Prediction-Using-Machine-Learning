# Maize-Yield-Prediction-Using-Machine-Learning
This project focuses on developing a predictive model to estimate maize yield in Zimbabwe using machine learning techniques. Agriculture is a vital part of Zimbabwe’s economy, and maize is one of its staple crops. The main objective of this project is to leverage data-driven methods to provide more reliable yield predictions.

Maize Yield Prediction Using Machine Learning

📌 Project Overview
This project aims to build a predictive system for estimating maize crop yields in Zimbabwe using historical agricultural and climatic data. It uses supervised machine learning algorithms to analyze and predict maize yield based on various factors such as rainfall, temperature, soil quality, and fertilizer use.

🎯 Objectives
- To enhance the accuracy of maize yield prediction by leveraging machine learning algorithms and techniques.
- To evaluate model performance using appropriate metrics (R² Score, RMSE, MAE).
- To help farmers and policymakers in Zimbabwe make informed agricultural decisions.

🧰 Technologies & Tools Used
- *Programming Language*: Python  
- *Libraries*:  
  - Pandas  
  - NumPy  
  - Scikit-learn  
  - Matplotlib / Seaborn (for visualization)  
Algorithms Used:  
  - Random Forest Regression  
  - Lasso Regression  
  - Linear Regression  
  - Decision Tree Regression  

📊 Dataset
- Historical data collected from open sources, research papers, and local agricultural agencies.
- Key features include:  
  - Annual rainfall  
  - Average temperature  
  - Fertilizer usage  
  - Soil pH level
  - Farming Districts in Zimbabwe
  - Pesticide 
  - Maize yield (target variable)

⚙️ How to Use

1. *Clone the Repository*
   bash
   git clone https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning.git
cd Maize-Yield-Prediction-Using-Machine-Learning

2. *Install Requirements*
   bash
   pip install -r requirements.txt
   
3. *Run the Script*
   bash
   python app.py
   
🔍 Project Structure

maize-yield-prediction/

├── data/                      # CSV datasets

├── notebooks/                 # Jupyter analysis notebooks

├── src/                       # Python scripts (data cleaning, model training)

│   └── model.py

│   └── preprocess.py

├── main.py                    # Entry point for training/testing

├── requirements.txt

└── README.me

✅ Results
- Random Forest Regression gave the highest accuracy with an R² score of *0.89*.
- Decision Tree and Linear Regression also performed reasonably but with higher error margins.
- Lasso helped in reducing overfitting by selecting relevant features.
  
# Screenshots

![welcome user](https://github.com/user-attachments/assets/f83ef678-7d5d-4a90-84f7-de6bd646b769)

![admin dashboard](https://github.com/user-attachments/assets/3a65db2d-e3ac-407d-b24d-716b9624df56)

<img width="1343" height="751" alt="admin add user" src="https://github.com/user-attachments/assets/0e85fc59-3618-4112-9f7c-46079944b2ea" /> 

<img width="1348" height="759" alt="Admin validation" src="https://github.com/user-attachments/assets/36278f45-19f0-498e-b775-605713562547" /> 

<img width="1343" height="637" alt="maize distribution1" src="https://github.com/user-attachments/assets/d18056f4-cc46-403e-bf73-e93f7d0d7c6f" />

<img width="1248" height="589" alt="pesticide 1" src="https://github.com/user-attachments/assets/c4afea8c-7fd6-49c6-a45a-fc6a48af23df" /> 

<img width="1339" height="658" alt="yield pesticides" src="https://github.com/user-attachments/assets/9bd372f1-ca28-4ebd-8c68-ec15dab33eb3" />

<img width="1338" height="663" alt="trend and years" src="https://github.com/user-attachments/assets/fb3f0a91-698c-49ff-9410-b3cdf39e504d" />   

<img width="1313" height="582" alt="temperature" src="https://github.com/user-attachments/assets/aec41fd4-0be0-4f36-a915-868a48b0b3f8" />

<img width="1237" height="588" alt="time" src="https://github.com/user-attachments/assets/b31432bb-f55a-475c-a2d7-d8810ea3e762" />

<img width="1351" height="699" alt="correlation heatmap" src="https://github.com/user-attachments/assets/f8ddda19-d841-419b-9780-638fd6810900" />




🔁 Future Improvements
- Integrate real-time weather APIs for dynamic predictions.
- Deploy the model using Flask or Streamlit for farmers' use.
- Include satellite imagery data for improved spatial accuracy.

🙏 Acknowledgements

Thanks to Zimbabwe’s Ministry of Agriculture, weather services that is Meteorological Services Department of Zimbabwe (MSD) and open data contributors for access to essential data.
