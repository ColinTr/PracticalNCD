# Software Name : PracticalNCD
# Version: 1.0
# SPDX-FileCopyrightText: Copyright (c) 2023 Orange
# SPDX-License-Identifier: MIT
#
# This software is distributed under the MIT License,
# the text of which is available at https://spdx.org/licenses/MIT.html
# or see the "license.txt" file for more details.

from sklearn.metrics import accuracy_score
from sklearn.cluster import KMeans
from tqdm import tqdm
import wandb
import math

from models.NCD_Spectral_Clustering import ncd_spectral_clustering
from models.NCD_Kmeans import k_means_pp
from src.utils import *


class PBNModel(nn.Module):
    def __init__(self, model_config):
        super(PBNModel, self).__init__()

        self.use_norm = model_config['use_norm']
        self.clustering_model = model_config['clustering_model']

        layers_dims = model_config['hidden_layers_dims'] + [model_config['latent_dim']]

        # (1) Encoder
        self.encoder_layers = []

        # (1.1) First layer:
        self.encoder_layers.append(nn.Linear(model_config['input_size'], layers_dims[0]))

        # (1.2) Hidden layers:
        if len(layers_dims) > 1:
            for i in range(1, len(layers_dims)):
                if model_config['activation_fct'] is not None:
                    self.encoder_layers.append(get_activation_function(model_config['activation_fct']))
                if model_config['use_batchnorm'] is True:
                    self.encoder_layers.append(nn.BatchNorm1d(num_features=layers_dims[i - 1]))
                if model_config['p_dropout'] > 0:
                    self.encoder_layers.append(nn.Dropout(p=model_config['p_dropout']))
                self.encoder_layers.append(nn.Linear(layers_dims[i - 1], layers_dims[i]))

        self.encoder_layers = nn.Sequential(*self.encoder_layers)

        # (2) Decoder
        self.decoder_layers = []
        decoder_layers_dims = list(reversed(layers_dims))

        # (2.1) Hidden layers:
        if len(decoder_layers_dims) > 1:
            for i in range(1, len(decoder_layers_dims)):
                self.decoder_layers.append(nn.Linear(decoder_layers_dims[i - 1], decoder_layers_dims[i]))
                if model_config['activation_fct'] is not None:
                    self.decoder_layers.append(get_activation_function(model_config['activation_fct']))
                if model_config['use_batchnorm'] is True:
                    self.decoder_layers.append(nn.BatchNorm1d(num_features=decoder_layers_dims[i]))
                if model_config['p_dropout'] > 0:
                    self.decoder_layers.append(nn.Dropout(p=model_config['p_dropout']))

        # (2.2) Last layer:
        self.decoder_layers.append(nn.Linear(decoder_layers_dims[-1], model_config['input_size']))

        self.decoder_layers = nn.Sequential(*self.decoder_layers)

        # (3) Classication layer
        self.classifier = nn.Linear(model_config['latent_dim'], model_config['n_classes'])

    def apply_norm(self, x):
        if self.use_norm is None:
            return x
        elif self.use_norm == "l1":
            return x / torch.linalg.norm(x, dim=1, ord=1).unsqueeze(-1)
        elif self.use_norm == "l2":
            return x / torch.linalg.norm(x, dim=1, ord=2).unsqueeze(-1)
        else:
            raise ValueError(f"Unknown norm: {self.use_norm}")

    def encoder_forward(self, x):
        z = self.encoder_layers(x)
        z = self.apply_norm(z)
        return z

    def decoder_forward(self, encoded_x):
        return self.decoder_layers(encoded_x)

    def classifier_forward(self, encoded_x):
        return self.classifier(encoded_x)

    def predict_new_data(self, n_clusters, x_unknown, x_known=None, y_known=None):
        self.eval()
        with torch.no_grad():
            projected_x_unknown = self.encoder_layers(x_unknown)

            if self.clustering_model == "kmeans":
                km = KMeans(n_clusters=n_clusters, init='k-means++', n_init=10)
                clustering_prediction = km.fit_predict(projected_x_unknown.cpu().numpy())
            elif self.clustering_model == "ncd_kmeans":
                projected_x_known = self.encoder_layers(x_known)

                known_classes_prototypes = torch.stack(
                    [projected_x_known[y_known == c].mean(axis=0) for c in np.unique(y_known)])
                kmpp = k_means_pp(pre_centroids=known_classes_prototypes, k_new_centroids=n_clusters)
                kmpp.fit(projected_x_unknown, tolerance=1e-10, n_iterations=1000, n_init=10)
                clustering_prediction = kmpp.predict_unknown_data(projected_x_unknown).cpu().numpy()
            elif self.clustering_model == "spectral_clustering":
                # My Spectral Clustering
                nsc = ncd_spectral_clustering(n_new_clusters=n_clusters,
                                              n_components=None,
                                              n_init=10,
                                              min_dist=0.6,
                                              assign_labels="ncd_kmeans",
                                              normed_laplacian=True)
                clustering_prediction = nsc.fit_predict_simple(projected_x_unknown)
            elif self.clustering_model == "ncd_spectral_clustering":
                projected_x_known = self.encoder_layers(x_known)

                nsc = ncd_spectral_clustering(n_new_clusters=n_clusters,
                                              n_components=None,
                                              n_init=10,
                                              min_dist=0.6,
                                              assign_labels="ncd_kmeans",
                                              normed_laplacian=True)
                clustering_prediction = nsc.fit_predict_known_and_unknown(projected_x_unknown, projected_x_known,
                                                                          y_known)
            else:
                raise ValueError(f"Unknown clustering model: {self.clustering_model}")
        self.train()

        return clustering_prediction

    def evaluate_classif_accuracy(self, x_known, y_known):
        self.eval()
        with torch.no_grad():
            y_pred = self.classifier_forward(self.encoder_forward(x_known))
            y_pred = F.softmax(y_pred, -1).argmax(dim=1)
        self.train()
        return accuracy_score(y_known, y_pred.cpu())

    def train_on_known_classes(self,
                               x_train, y_train, unknown_class_value,
                               x_test_unknown, y_test_unknown,
                               x_test_known, y_test_known,
                               batch_size, lr, epochs, w, clustering_runs=10,
                               evaluate=True, use_wandb=False, disable_tqdm=False):
        losses_dict = {
            'train_losses': [],
            'train_ce_losses': [],
            'train_mse_losses': [],

            'train_classification_accuracy': [],
            'test_classification_accuracy': [],
            'test_average_clustering_accuracy': [],
        }

        optimizer = torch.optim.AdamW(self.parameters(), lr=lr)

        ce_loss_func = nn.CrossEntropyLoss()
        mse_loss_func = nn.MSELoss(reduction="sum")

        n_batchs = math.ceil((x_train.shape[0]) / batch_size)

        with tqdm(range(epochs * n_batchs), disable=disable_tqdm) as t:
            for epoch in range(epochs):
                t.set_description("Epoch " + str(epoch + 1) + " / " + str(epochs))

                train_losses, train_ce_losses, train_mse_losses = [], [], []

                batch_start_index, batch_end_index = 0, min(batch_size, len(x_train))
                for batch_index in range(n_batchs):
                    batch_x_train = x_train[batch_start_index:batch_end_index]
                    batch_y_train = y_train[batch_start_index:batch_end_index]
                    batch_y_train = torch.tensor(batch_y_train, dtype=torch.int64, device=x_train.device)
                    mask_known = batch_y_train != unknown_class_value
                    
                    if len(batch_x_train) < 2:
                        print("Skipping batch of size 1...")
                        continue

                    optimizer.zero_grad()

                    # ========== forward ==========
                    # (1) Encode all the data
                    encoded_batch_x = self.encoder_forward(batch_x_train)

                    # (2) Reconstruct all the data
                    reconstructed_batch_x = self.decoder_forward(encoded_batch_x)

                    # (3) Learn to classify the known data only
                    y_known_pred = self.classifier_forward(encoded_batch_x[mask_known])
                    # =============================

                    ce_loss = ce_loss_func(y_known_pred, batch_y_train[mask_known])
                    mse_loss = mse_loss_func(reconstructed_batch_x, batch_x_train) / len(batch_x_train)

                    full_loss = w * ce_loss + (1 - w) * mse_loss

                    full_loss.backward()

                    optimizer.step()

                    # Save loss for plotting purposes
                    train_losses.append(full_loss.item())
                    train_ce_losses.append(ce_loss.item())
                    train_mse_losses.append(mse_loss.item())

                    t.set_postfix_str("full={:05.3f} | ce={:05.3f} | mse={:05.3f}".format(np.mean(train_losses),
                                                                                          np.mean(train_ce_losses),
                                                                                          np.mean(train_mse_losses)))
                    t.update()

                    batch_start_index += batch_size
                    batch_end_index = min((batch_end_index + batch_size), x_train.shape[0])

                losses_dict['train_losses'].append(np.mean(train_losses))
                losses_dict['train_ce_losses'].append(np.mean(train_ce_losses))
                losses_dict['train_mse_losses'].append(np.mean(train_mse_losses))

                if evaluate is True:
                    # Run the clustering method a few times and average the results
                    average_clust_acc = np.mean([hungarian_accuracy(
                        np.array(self.predict_new_data(x_test_unknown, x_test_known, y_test_known)),
                        np.array(y_test_unknown)) for _ in range(clustering_runs)])
                    losses_dict['test_average_clustering_accuracy'].append(average_clust_acc)

                    losses_dict['train_classification_accuracy'].append(
                        self.evaluate_classif_accuracy(x_train, y_train))
                    losses_dict['test_classification_accuracy'].append(
                        self.evaluate_classif_accuracy(x_test_known, y_test_known))

                if use_wandb is True:
                    wandb.log({k: losses_dict[k][-1] for k in losses_dict.keys() if len(losses_dict[k]) > 0})

        return losses_dict
