"""© 2018 Jianfei Gao All Rights Reserved

- Original Version

    Author: I-Ta Lee
    Date: 10/1/2017

- Modified Version

    Author: Jianfei Gao
    Date: 08/28/2018

"""
import argparse
import logging
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from my_neural_networks import utils, networks, mnist, example_networks
from my_neural_networks.minibatcher import MiniBatcher


def get_arguments(argv):
    parser = argparse.ArgumentParser(description='Training for MNIST')
    parser.add_argument('data_folder', metavar='DATA_FOLDER',
                        help='the folder that contains all the input data')

    parser.add_argument('-e', '--n_epochs', type=int, default=100,
                        help='number of epochs (DEFAULT: 100)')
    parser.add_argument('-l', '--learning_rate', type=float, default=1e-4,
                        help='learning rate for gradient descent (DEFAULT: 1e-4)')
    parser.add_argument('-i', '--impl', choices=['torch.nn', 'torch.autograd', 'my'], default='my',
                        help='choose the network implementation (DEFAULT: my)')
    parser.add_argument('-g', '--gpu_id', type=int, default=-1,
                        help='gpu id to use. -1 means cpu (DEFAULT: -1)')
    parser.add_argument('-a', '--architecture', type=int, default=4,
                        help='number of layers. (DEFAULT: 4)')

    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='show info messages')
    parser.add_argument('-d', '--debug', action='store_true', default=False,
                        help='show debug messages')
    args = parser.parse_args(argv)
    return args


def one_hot(y, n_classes):
    """Encode labels into ont-hot vectors
    """
    m = y.shape[0]
    y_1hot = np.zeros((m, n_classes), dtype=np.float32)
    y_1hot[np.arange(m), np.squeeze(y)] = 1
    return y_1hot


def save_plots(batches, train_losses, test_losses, train_accs, test_accs):
    """Plot

        Plot two figures: loss vs. epoch and accuracy vs. epoch
    """
    n = len(train_losses)
    xs = np.arange(n)

    # plot losses
    fig, ax = plt.subplots()
    ax.plot(batches, train_losses, '--', linewidth=2, label='train')
    ax.plot(batches, test_losses, '-', linewidth=2, label='test')
    ax.set_xlabel("Training Data Size")
    ax.set_ylabel("Loss")
    ax.legend(loc='lower right')
    plt.savefig('loss.png')

    # plot train and test accuracies
    plt.clf()
    fig, ax = plt.subplots()
    ax.plot(batches, train_accs, '--', linewidth=2, label='train')
    ax.plot(batches, test_accs, '-', linewidth=2, label='test')
    ax.set_xlabel("Training Data Size")
    ax.set_ylabel("Accuracy")
    ax.legend(loc='lower right')
    plt.savefig('accuracy.png')


def create_model(shape):
    logging.info('selec implementation: {}'.format(args.impl))
    if args.impl == 'torch.nn':
        # torch.nn implementation
        model = example_networks.TorchNeuralNetwork(shape,
                                                    gpu_id=args.gpu_id)
    elif args.impl == 'torch.autograd':
        # torch.autograd implementation
        model = networks.AutogradNeuralNetwork(shape,
                                               gpu_id=args.gpu_id)
    else:
        # our implementation
        model = networks.BasicNeuralNetwork(shape,
                                            gpu_id=args.gpu_id)
    return model


def main(n_samples):
    # DEBUG: fix seed
    torch.manual_seed(29)

    # load data
    X_train, y_train = mnist.load_train_data(args.data_folder, max_n_examples=n_samples)
    X_test, y_test = mnist.load_test_data(args.data_folder)

    # reshape the images into one dimension
    X_train = X_train.reshape((X_train.shape[0], -1))
    y_train_1hot = one_hot(y_train, mnist.N_CLASSES)
    X_test = X_test.reshape((X_test.shape[0], -1))
    y_test_1hot = one_hot(y_test, mnist.N_CLASSES)

    # to torch tensor
    X_train, y_train, y_train_1hot = torch.from_numpy(X_train), torch.from_numpy(y_train), torch.from_numpy(y_train_1hot)
    X_train = X_train.type(torch.FloatTensor)
    X_test, y_test, y_test_1hot = torch.from_numpy(X_test), torch.from_numpy(y_test), torch.from_numpy(y_test_1hot)
    X_test = X_test.type(torch.FloatTensor)

    # get network shape
    if args.architecture == 4:
        shape = [X_train.shape[1], 300, 100, mnist.N_CLASSES]
    elif args.architecture == 2:
        shape = [X_train.shape[1], mnist.N_CLASSES]
    else:
        raise RuntimeError("{} is not a focusing number of layers".format(args.architecture))

    # if we want to run it with torch.autograd, we need to use Variable
    if args.impl != 'my':
        X_train = torch.autograd.Variable(X_train, requires_grad=True)
        y_train = torch.autograd.Variable(y_train, requires_grad=False)
        y_train_1hot = torch.autograd.Variable(y_train_1hot, requires_grad=False)
        X_test = torch.autograd.Variable(X_test, requires_grad=True)
        y_test = torch.autograd.Variable(y_test, requires_grad=False)
        y_test_1hot = torch.autograd.Variable(y_test_1hot, requires_grad=False)

        n_examples = X_train.data.shape[0]
        logging.info("X_train shape: {}".format(X_train.data.shape))
        logging.info("X_test shape: {}".format(X_test.data.shape))
    else:
        n_examples = X_train.shape[0]
        logging.info("X_train shape: {}".format(X_train.shape))
        logging.info("X_test shape: {}".format(X_test.shape))

    # if gpu_id is specified
    if args.gpu_id != -1:
        # move all variables to cuda
        X_train = X_train.cuda(args.gpu_id)
        y_train = y_train.cuda(args.gpu_id)
        y_train_1hot = y_train_1hot.cuda(args.gpu_id)
        X_test = X_test.cuda(args.gpu_id)
        y_test = y_test.cuda(args.gpu_id)
        y_test_1hot = y_test_1hot.cuda(args.gpu_id)

    # create model
    model = create_model(shape)

    # start training
    train_losses = []
    test_losses = []
    train_accs = []
    test_accs = []
    best_test_acc = None
    # wihtout minibatch size, this only shuffles the indices
    batcher = MiniBatcher(n_examples, n_examples)
    for i_epoch in range(args.n_epochs):
        logging.info("---------- EPOCH {} ----------".format(i_epoch))

        for train_idxs in batcher.get_one_batch():
            # numpy to torch
            if args.gpu_id != -1:
                train_idxs = train_idxs.cuda(args.gpu_id)

            # fit to the training data
            loss = model.train_one_epoch(X_train[train_idxs], y_train[train_idxs], y_train_1hot[train_idxs], args.learning_rate)
            logging.info("loss = {}".format(loss))

            # monitor training and testing accuracy
            y_train_pred = model.predict(X_train)
            y_test_pred = model.predict(X_test)
            train_acc = utils.accuracy(y_train, y_train_pred)
            test_acc = utils.accuracy(y_test, y_test_pred)
            logging.info("Accuracy(train) = {}".format(train_acc))
            logging.info("Accuracy(test) = {}".format(test_acc))

        # only track the best model
        if best_test_acc is None or test_acc > best_test_acc:
            logging.info('Update')
            best_test_acc = test_acc
            torch.save(model, 'model.pt')
        else:
            logging.info('Discard')
            test_acc = best_test_acc

        # collect results for plotting for each epoch
        train_loss = model.loss(X_train, y_train, y_train_1hot)
        test_loss = model.loss(X_test, y_test, y_test_1hot)
        train_losses.append(train_loss)
        test_losses.append(test_loss)
        train_accs.append(train_acc)
        test_accs.append(test_acc)

    return train_losses, test_losses, train_accs, test_accs


def main2():
    batches = [250, 500, 1000, 2000, 4000, 8000, 10000]
    train_losses = []
    test_losses = []
    train_accs = []
    test_accs = []
    for bsz in batches:
        trloss, teloss, tracc, teacc = main(bsz)
        train_losses.append(trloss[-1])
        test_losses.append(teloss[-1])
        train_accs.append(tracc[-1])
        test_accs.append(teacc[-1])
    # plot
    save_plots(batches, train_losses, test_losses, train_accs, test_accs)


if __name__ == '__main__':
    args = utils.bin_config(get_arguments)
    main2()
