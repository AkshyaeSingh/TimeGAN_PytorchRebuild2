import numpy as np
import timegan
from metrics.discriminative_metrics import discriminative_score_metrics
from metrics.predictive_metrics import predictive_score_metrics
from metrics.visualization_metrics import visualization
from metrics.privacy_metrics import nearest_neighbor_distance_ratio, k_anonymity, l_diversity
from utils import extract_time


def train(opt, ori_data):

    # Model Setting
    model = timegan.TimeGAN(opt, ori_data)
    per_print_num = opt.iterations / opt.print_times

    # 1. Embedding network training
    print('Start Embedding Network Training')
    for i in range(opt.iterations):
        model.gen_batch()
        model.batch_forward()
        model.train_embedder()
        if i % per_print_num == 0:
            print('step: ' + str(i) + '/' + str(opt.iterations) +
                  ', e_loss: ' + str(np.round(np.sqrt(model.E_loss_T0.item()), 4)))
    print('Finish Embedding Network Training')

    # 2. Training only with supervised loss
    print('Start Training with Supervised Loss Only')
    for i in range(opt.iterations):
        model.gen_batch()
        model.batch_forward()
        model.train_supervisor()
        if i % per_print_num == 0:
            print('step: ' + str(i) + '/' + str(opt.iterations) +
                  ', e_loss: ' + str(np.round(np.sqrt(model.G_loss_S.item()), 4)))

    # 3. Joint Training
    print('Start Joint Training')
    for i in range(opt.iterations):
        # Generator training (twice more than discriminator training)
        for kk in range(2):
            model.gen_batch()
            model.batch_forward()
            model.train_generator(join_train=True)
            model.batch_forward()
            model.train_embedder(join_train=True)
        # Discriminator training
        model.gen_batch()
        model.batch_forward()
        model.train_discriminator()

        # Print multiple checkpoints
        if i % per_print_num == 0:
            print('step: ' + str(i) + '/' + str(opt.iterations) +
                  ', d_loss: ' + str(np.round(model.D_loss.item(), 4)) +
                  ', g_loss_u: ' + str(np.round(model.G_loss_U.item(), 4)) +
                  ', g_loss_s: ' + str(np.round(np.sqrt(model.G_loss_S.item()), 4)) +
                  ', g_loss_v: ' + str(np.round(model.G_loss_V.item(), 4)) +
                  ', e_loss_t0: ' + str(np.round(np.sqrt(model.E_loss_T0.item()), 4)))
    print('Finish Joint Training')

    # Save trained networks
    model.save_trained_networks()

def test(opt, ori_data):
    print('Start Testing')
    # Model Setting
    model = timegan.TimeGAN(opt, ori_data)
    model.load_trained_networks()

    # Synthetic data generation
    if opt.synth_size != 0:
        synth_size = opt.synth_size
    else:
        synth_size = len(ori_data)
    generated_data = model.gen_synth_data(synth_size)
    generated_data = np.array(generated_data.cpu().detach().numpy())
    gen_data = list()
    for i in range(synth_size):
        temp = generated_data[i, :opt.seq_len, :]
        gen_data.append(temp)
    print('Finish Synthetic Data Generation')

    # Performance metrics
    metric_results = dict()
    if not opt.only_visualize_metric:
        # 1. Discriminative Score
        discriminative_score = list()
        print('Start discriminative_score_metrics')
        for i in range(opt.metric_iteration):
            print(f'discriminative_score iteration: {i}')
            try:
                temp_disc = discriminative_score_metrics(ori_data, gen_data)
                print(f"Iteration {i} discriminative score: {temp_disc}")
                discriminative_score.append(temp_disc)
            except Exception as e:
                print(f"Error in discriminative_score_metrics at iteration {i}: {e}")
        if discriminative_score:
            metric_results['discriminative'] = np.mean(discriminative_score)
            print(f'Finish discriminative_score_metrics compute: {metric_results["discriminative"]}')
        else:
            print('Discriminative score list is empty.')

        # 2. Predictive score
        predictive_score = list()
        print('Start predictive_score_metrics')
        for i in range(opt.metric_iteration):
            print(f'predictive_score iteration: {i}')
            try:
                temp_predict = predictive_score_metrics(ori_data, gen_data)
                print(f"Iteration {i} predictive score: {temp_predict}")
                predictive_score.append(temp_predict)
            except Exception as e:
                print(f"Error in predictive_score_metrics at iteration {i}: {e}")
        if predictive_score:
            metric_results['predictive'] = np.mean(predictive_score)
            print(f'Finish predictive_score_metrics compute: {metric_results["predictive"]}')
        else:
            print('Predictive score list is empty.')

        # 3. Nearest Neighbor Distance Ratio (NNDR)
        print('Start nearest_neighbor_distance_ratio')
        try:
            nndr = nearest_neighbor_distance_ratio(ori_data, gen_data)
            print(f"NNDR: {nndr}")
            metric_results['nndr'] = nndr
            print('Finish nearest_neighbor_distance_ratio compute')
        except Exception as e:
            print(f'NNDR computation failed: {e}')

        # 4. K-Anonymity
        print('Start k_anonymity')
        try:
            k_anonym = k_anonymity(gen_data, k=5)
            print(f"K-Anonymity: {k_anonym}")
            metric_results['k_anonymity'] = k_anonym
            print('Finish k_anonymity compute')
        except Exception as e:
            print(f'K-Anonymity computation failed: {e}')

        # 5. L-Diversity
        print('Start l_diversity')
        try:
            l_div = l_diversity(gen_data, sensitive_attribute_idx=0, l=2)
            print(f"L-Diversity: {l_div}")
            metric_results['l_diversity'] = l_div
            print('Finish l_diversity compute')
        except Exception as e:
            print(f'L-Diversity computation failed: {e}')

    # 6. Visualization (PCA and tSNE)
    visualization(ori_data, gen_data, 'pca', opt.output_dir)
    visualization(ori_data, gen_data, 'tsne', opt.output_dir)

    # Print all metrics
    print("Metric Results:", metric_results)
