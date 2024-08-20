<p align="center">
  <h1 align="center">PracticalNCD</h1>
 
  Code used to generate the results of the DMKD journal paper <a href="https://arxiv.org/pdf/2311.05440.pdf">A Practical Approach to Novel Class Discovery in Tabular Data</a>
</p>

<div align="center">
 
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>


## 🔍 Overview
This python library proposes an ensemble tools for the Machine Learning problem of [Novel Class Discovery](https://arxiv.org/pdf/2302.12028.pdf).

In this library, you will find the following tools illustrated through Jupyter Notebooks:
 - An hyperparameter optimization procedure tailored to transfer the results from the known classes to the novel classes.
 - An estimation of the number of clusters by applying clustering quality metrics in the latent space of NCD methods.
 - Two unsupervised clustering algorithms modified to utilize the data available in the NCD setting.
 - A novel method called PBN (for Projection-Based NCD).


## 🐍 Setting up the Python environment

### Option 1 - With [Anaconda](https://www.anaconda.com/download):

```bash
# Create the virtual environment and install the packages with conda
conda env create --file environment.yml --prefix ./venvpracticalncd

# Activate the virtual environment
conda activate .\venvpracticalncd

# Add package missing from conda repositories
pip install iteration-utilities==0.11.0
```

### Option 2 - Without Anaconda:

Prerequisite: having [Python 3.10.9](https://www.python.org/downloads/release/python-3109/) the default python 3.10 version.

```bash
# Create the empty virtual environment
py -3.10 -m venv venvpracticalncd

# Activate the virtual environment
# On windows:
  .\venvpracticalncd\Scripts\activate
# On linux:
  source venvpracticalncd/bin/activate
  
# Install the needed packages
pip install -r requirements.txt

# And finish by installing pytorch independently
pip install torch==1.12.1 --index-url https://download.pytorch.org/whl/cu113
```


### Finishing touches

```bash
# Add the virtual environment as a jupyter kernel
ipython kernel install --name "venvpracticalncd" --user

# Check if torch supports GPU (you need CUDA 11 installed)
python -c "import torch; print(torch.cuda.is_available())"
```


## 💻 Usage
Three notebooks are available:
- **Full_notebook.ipynb** lets you train and evaluate the models when the number of clusters *k* is known in advance.
- **Full_notebook_with_k_estimation.ipynb** (self-explanatory).
- **results_wrt_n_unknown_classes.ipynb** is used to evaluate the performance of all the models when the number of novel classes increases. It was used to generate Figure C1 of Appendix C.


## 📊 Datasets
The datasets will be <u>automatically downloaded</u> from https://archive.ics.uci.edu/ on the first execution.<br/>
If it fails, please try disabling proxies.

**However**, the data splits for some datasets are random and the results can vary compared to the paper.

The most impacted datasets are:
- LetterRecognition
- USCensus1990
- multiple_feature


## 📜 Citation
If you found this work useful, please use the following citation:
```
@article{tr2024practical,
   title = {A Practical Approach to Novel Class Discovery in Tabular Data},
   author = {Troisemaine, Colin and Reiffers{-}Masson, Alexandre and Gosselin, St{'{e}}phane and Lemaire, Vincent and Vaton, Sandrine},
   journal = {Data Mining and Knowledge Discovery},
   year = {2024},
   month = {May},
   day = {31},
   issn = {1573-756X},
   doi = {10.1007/s10618-024-01025-y}
}
```

## License

Copyright (c) 2023 Orange.

This code is released under the MIT license. See the LICENSE file for more information.
