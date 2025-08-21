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

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/welcome%20user.jpg

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/Admin%20validation.PNG 

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/admin%20dashboard.jpg

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/GUI-%20login.PNG

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/correlation%20heatmap.PNG 

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/maize%20distribution.PNG

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/pesticides.PNG 

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/trend%20and%20years.PNG

https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/blob/main/screenshots/yield%20pesticides.PNG




🔁 Future Improvements
- Integrate real-time weather APIs for dynamic predictions.
- Deploy the model using Flask or Streamlit for farmers' use.
- Include satellite imagery data for improved spatial accuracy.

🙏 Acknowledgements

Thanks to Zimbabwe’s Ministry of Agriculture, weather services that is Meteorological Services Department of Zimbabwe (MSD) and open data contributors for access to essential data.
