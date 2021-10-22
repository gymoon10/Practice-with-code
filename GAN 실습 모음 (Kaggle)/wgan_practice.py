# -*- coding: utf-8 -*-
"""WGAN_practice.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1O5T_PDFcWSdY00r611fdG8ickDPGQzYh

## Wasserstein GAN

GAN의 목적은 확률 분포를 학습하는 것이지만, 저차원의 manifold에 의해 support되는 분포를 학습하는 것은 매우 어려운 일.

이 경우 모델의 manifold와 실제 분포의 support의 교집합이 거의 없는 문제가 발생할 수 있음.

![image](https://user-images.githubusercontent.com/44194558/138078788-93863b02-1167-4dd4-9980-97d743586d3e.png)

기존의 JS 방식은 동일한 support를 공유하는 분포에 대해서만 정의가 가능하기 때문에, 고차원의 원본 데이터 공간에서 작은 manifold를 생성해야 하는 생성 문제에 한계를 가짐. (작은 manifold 세트는 supoort를 공유하기 어려움)


WGAN의 critic은 생성된 이미지의 realness에 대한 점수를 출력.

**EM distance**

노이즈의 각 점을 이산 확률 분포로 처리한 다음, 실제 데이터 분포의 실제 포인트와 생성된 데이터 분포의 가짜 포인트 사이의 유클리드 거리를 계산.

학습의 목표는 실제 데이터 분포와 가짜 데이터 분포에서 포인트 사이의 거리 합(cost)를 최소화 하는 것. EM distance를 통해 각 데이터 포인트가 출력에 어떠한 영향을 미치는지 를 파악할 수 있음. 

![image](https://user-images.githubusercontent.com/44194558/138078722-200a0d78-6f79-4ac1-b319-1a80cf187c38.png)
"""

# Commented out IPython magic to ensure Python compatibility.
# %load_ext tensorboard

import os
from glob import glob
import time
import random

import IPython.display as display
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import PIL
from PIL import Image
import imageio
import numpy as np

import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras.initializers import RandomNormal
# %matplotlib inline

from google.colab import drive
drive.mount('/content/drive')

"""### Configs"""

# Experiment paths
# 훈련된 모델 저장
EXPERIMENT_ID = "train_wgan"
MODEL_SAVE_PATH = os.path.join("/content/drive/My Drive/wgan/results", EXPERIMENT_ID)
if not os.path.exists(MODEL_SAVE_PATH):
    os.makedirs(MODEL_SAVE_PATH)
CHECKPOINT_DIR = os.path.join(MODEL_SAVE_PATH, 'training_checkpoints')

# Data path
DATA_PATH =   "/content/drive/My Drive/DCGAN_PRACTICE/datasets/cars/cars_images/"  # DCGAN 실습에 사용했던 자동차 이미지 사용

# Model parameters
BATCH_SIZE = 64
EPOCHS = 9000
LATENT_DEPTH = 100
IMAGE_SHAPE = [100, 100]
NB_CHANNELS = 3
LR = 1e-4
BETA = 0.5
NOISE = tf.random.normal([1, LATENT_DEPTH])

# CRITIC parameters 
N_CRITIC = 5
CLIPPING_WEIGHT = 0.01  

seed = random.seed(30)

# DATA_PATH 경로의 모든 이미지 파일 불러오기
cars_images_path = list(glob(str(DATA_PATH + '*.jpg')))

images_name = [i.split(DATA_PATH) for i in cars_images_path]
images_name = [x[:][1] for x in images_name]
cars_model = [i.split('_')[0] for i in images_name]

"""## Data Loader (TF API 사용)"""

@tf.function
def preprocessing_data(path):
    image = tf.io.read_file(path)
    image = tf.image.decode_jpeg(image, channels=3)
    image = tf.image.resize(image, [IMAGE_SHAPE[0],IMAGE_SHAPE[1]])
    image = image / 255.0
    return image

def dataloader(paths):
    dataset = tf.data.Dataset.from_tensor_slices(paths)
    dataset = dataset.shuffle(buffer_size=len(paths))
    dataset = dataset.map(preprocessing_data)
    dataset = dataset.batch(10* BATCH_SIZE)
    dataset = dataset.prefetch(1)
    return dataset

dataset = dataloader(cars_images_path)
for batch in dataset.take(1):
    for img in batch:
        img_np = img.numpy()
        plt.figure()
        plt.axis('off')
        plt.imshow((img_np-img_np.min())/(img_np.max()-img_np.min()))

"""## Modeling

![image](https://user-images.githubusercontent.com/44194558/138080259-2f34e11f-3b9d-4885-a9d5-1d5a64fa844f.png)

1. output layer에 선형 활성화 함수를 추가하거나, 시그모이드 함수를 사용하고 있으면 제거

2. critic, 생성자의 학습을 위해 Wasserstein loss를 사용. 진짜와 가짜 이미지에 대한 realness 점수 차이가 크게 나도록.

3. 미니 배치에 대한 업데이트 후 weight range에 대한 제약을 추가 (논문에서는 [-0.01, 0.01]

4. 매 iteration마다 critic을 생성자보다 많이 훈련시킴 (논문에서는 5회)

5. RMSProp 사용 (논문에서 사용하는 0.00005 같이 낮은 학습률, momentum x)


모델링 참고 : https://zzu0203.github.io/deeplearning/WGAN-imple/

### Generator

![image](https://user-images.githubusercontent.com/44194558/138081070-db11785f-11c9-4580-beac-46c1946d9183.png)

기존 GAN과 차이 없음
"""

def make_generator_model():
    # 가중치 초기화의 경우 init = RandomNormal(stddev=0.02)
    model = tf.keras.Sequential()
    model.add(layers.Dense(25*25*128, use_bias=False, input_shape=(100, ))) # add kernel_initializer=init in case of weight initialization
    model.add(layers.BatchNormalization())
    model.add(layers.ReLU())
    model.add(layers.Reshape((25, 25, 128)))
    assert model.output_shape == (None, 25, 25, 128)

    model.add(layers.Conv2DTranspose(128, (5, 5), strides=(1, 1), padding='same', use_bias=False))# add kernel_initializer=init in case of weight initialization
    assert model.output_shape == (None, 25, 25, 128)
    model.add(layers.BatchNormalization())
    model.add(layers.ReLU())

    model.add(layers.Conv2DTranspose(64, (5, 5), strides=(2, 2), padding='same', use_bias=False))# add kernel_initializer=init in case of weight initialization
    assert model.output_shape == (None, 50, 50, 64)
    model.add(layers.BatchNormalization())
    model.add(layers.ReLU())
    
    model.add(layers.Conv2DTranspose(3, (5, 5), strides=(2, 2), padding='same', use_bias=False, activation='sigmoid'))# add kernel_initializer=init in case of weight initialization
    assert model.output_shape == (None, 100, 100, 3)
    model.summary()
    return model

generator = make_generator_model()
noise = tf.random.normal([1, LATENT_DEPTH])
generated_image = generator(noise, training=True)

plt.imshow(generated_image[0, :, :, :], cmap='gray')

"""### Critic

이진 분류 대신 실제 이미지, 생성된 이미지에 대한 점수 출력 (sigmoid를 쓰지 않는 이유)

주어진 이미지에 대한 realness 점수를 예측하기 위해 linear activation이 필요함.
"""

def make_critic_model():
    model = tf.keras.Sequential()
    model.add(layers.Conv2D(64, (5, 5), strides=(2, 2), padding='same', input_shape=[100, 100, 3]))
    model.add(layers.ReLU(0.2))
    model.add(layers.Dropout(0.3))

    model.add(layers.Conv2D(128, (5, 5), strides=(2, 2), padding='same'))
    model.add(layers.ReLU())
    model.add(layers.Dropout(0.3))

    model.add(layers.Flatten())
    model.add(layers.Dense(1)) #activation='linear' (default)
    model.summary()

    return model

critic = make_critic_model()
decision = critic(generated_image)
print (decision)

"""### Loss and Optimization

모델과 실제 분포의 차이를 계산하기 위해 Wasserstein distance 사용.

DCGAN은 판별자를 이진 분류 모델로 훈련하여 주어진 이미지가 실제일 확률을 예측 (binary cross entropy로 생성자, 판별자를 훈련하고 업데이트)

WGAN의 주요 기여는 판별자가 주어진 입력이 얼마나 실제인지 가짜인지에 대한 점수를 예측하도록 장려하는 새로운 손실함수를 사용한다는 것.

판별자의 역할을 이미지의 realness를 평가하는 critic으로 변환. (생성된 이미지와 실제 이미지 점수 간의 차이는 가능한 크게)
"""

def critic_loss(r_logit, f_logit):
    # critic_loss(d_loss)는 K.mean(real_output) - K.mean(fake_output)의 형식. 점수 차이를 크게 해야 함 
    real_loss = - tf.reduce_mean(r_logit)  # 실제 이미지에서는 최대화
    fake_loss = tf.reduce_mean(f_logit)  # 가짜 이미지에서는 최소화

    return real_loss, fake_loss

def generator_loss(f_logit):
    fake_loss = - tf.reduce_mean(f_logit)

    return fake_loss

# 그냥 Adam으로 시도해봄 (논문은 RMSprop)
generator_optimizer = tf.keras.optimizers.Adam(learning_rate= LR) #tf.keras.optimizers.RMSprop(learning_rate= LR)
critic_optimizer = tf.keras.optimizers.Adam(learning_rate= LR) #tf.keras.optimizers.RMSprop(learning_rate= LR)

"""## Experiment utils"""

def summary(name_data_dict,
            step=None,
            types=['mean', 'std', 'max', 'min', 'sparsity', 'histogram'],
            historgram_buckets=None,
            name='summary'):
    """Summary.
    Examples
    --------
    >>> summary({'a': data_a, 'b': data_b})
    """
    def _summary(name, data):
        if data.shape == ():
            tf.summary.scalar(name, data, step=step)  # 텐서보드 로그 가져오기
        else:
            if 'mean' in types:
                tf.summary.scalar(name + '-mean', tf.math.reduce_mean(data), step=step)
            if 'std' in types:
                tf.summary.scalar(name + '-std', tf.math.reduce_std(data), step=step)
            if 'max' in types:
                tf.summary.scalar(name + '-max', tf.math.reduce_max(data), step=step)
            if 'min' in types:
                tf.summary.scalar(name + '-min', tf.math.reduce_min(data), step=step)
            if 'sparsity' in types:
                tf.summary.scalar(name + '-sparsity', tf.math.zero_fraction(data), step=step)
            if 'histogram' in types:
                tf.summary.histogram(name, data, step=step, buckets=historgram_buckets)

    with tf.name_scope(name):
        for name, data in name_data_dict.items():
            _summary(name, data)

train_summary_writer = tf.summary.create_file_writer(os.path.join(MODEL_SAVE_PATH, 'summaries', 'train'))

checkpoint_prefix = os.path.join(CHECKPOINT_DIR, "ckpt")
checkpoint = tf.train.Checkpoint(generator_optimizer=generator_optimizer,
                                 discriminator_optimizer=critic_optimizer,
                                 generator=generator,
                                 discriminator=critic)

def generate_and_save_images(model, epoch, noise):
    
    plt.figure(figsize=(15,10))

    for i in range(4):
        images = model(noise, training=False)
        
        image = images[0, :, :, :]
        image = np.reshape(image, [100, 100, 3])
        
        plt.subplot(1, 4, i+1)
        plt.imshow(np.uint8(image), cmap='gray')
        plt.axis('off')
        plt.title("Randomly Generated Images")

    plt.tight_layout()  
    plt.savefig(os.path.join(MODEL_SAVE_PATH,'image_at_epoch_{:02d}.png'.format(epoch)))
    plt.show()

"""## Training Process"""

@ tf.function
def train_generator(noise):
    # 주어진 입력 변수에 대한 연산의 gradient를 자동 계산. 실행된 모든 연산이 Tape에 기록됨
    with tf.GradientTape() as tape:
        generated_images = generator(noise, training=True)  # 생성자가 가짜 이미지를 생성
        fake_logit = critic(generated_images, training=True)  # critic이 생성된 이미지에 대한 점수를 출력
        g_loss = generator_loss(fake_logit)  # 해당 점수를 이용하여 loss 계산

    gradients = tape.gradient(g_loss, generator.trainable_variables)  # 생성자의 loss에 대한 gradient
    generator_optimizer.apply_gradients(zip(gradients, generator.trainable_variables))   # 생성자의 가중치만 업데이트 (critic은 따로)

    return {'Generator loss': g_loss}

"""![image](https://user-images.githubusercontent.com/44194558/138084528-a6aed106-ea7c-47d8-8558-0801543fc1d5.png)

GradientTape 참고 : https://teddylee777.github.io/tensorflow/gradient-tape

training=True 참고 : https://stackoverflow.com/questions/57320371/what-does-training-true-mean-when-calling-a-tensorflow-keras-model
"""

@tf.function
def train_Critic(noise, real_img):
    with tf.GradientTape() as t:
        fake_img = generator(noise, training=True)
        
        # 가짜, 진짜 이미지에 대한 realness 점수
        real_logit = critic(real_img, training=True)
        fake_logit = critic(fake_img, training=True)
        
        # critic loss (d_loss)
        real_loss, fake_loss = critic_loss(real_logit, fake_logit)
        d_loss = (real_loss + fake_loss)

    D_grad = t.gradient(d_loss, critic.trainable_variables)
    critic_optimizer.apply_gradients(zip(D_grad, critic.trainable_variables))  # critic만 훈련됨 (두 네트워크는 별도로 훈련)
    
    # weight clipping을 적용시켜 립시츠 제약 조건을 강제
    for w in critic.trainable_variables:
        w.assign(tf.clip_by_value(w, -CLIPPING_WEIGHT, -CLIPPING_WEIGHT))

    return {'Critic loss': real_loss + fake_loss}

def train(dataset, epochs):
    with train_summary_writer.as_default():
        with tf.summary.record_if(True):
            for epoch in range(epochs):
                start = time.time()
                for image_batch in dataset:
                    C_loss_dict = train_Critic(NOISE, image_batch)

                summary(C_loss_dict, step=critic_optimizer.iterations, name='critic_losses')

                if critic_optimizer.iterations.numpy() % N_CRITIC == 0:   # 생성자 모델의 각 업데이트에 대해 critic이 업데이트되는 횟수를 제어하는 하이퍼 파라미터(5)
                    G_loss_dict = train_generator(NOISE)
                    summary(G_loss_dict, step=generator_optimizer.iterations, name='generator_losses')

                display.clear_output(wait=True)
                generate_and_save_images(generator,
                                         epoch + 1, NOISE)
                
                if (epoch + 1) % 15 == 0:
                    checkpoint.save(file_prefix = checkpoint_prefix)

                print ('Time for epoch {} is {} sec'.format(epoch + 1, time.time()-start))

    display.clear_output(wait=True)
    generate_and_save_images(generator, epochs, NOISE)

# Commented out IPython magic to ensure Python compatibility.
# %tensorboard --logdir='/content/drive/My Drive/wgan/results/summaries'

train(dataset, EPOCHS)

# Commented out IPython magic to ensure Python compatibility.
# %tensorboard --logdir='/content/drive/My Drive/wgan/results/summaries'

anim_file = 'wgan.gif'

with imageio.get_writer(anim_file, mode='I') as writer:
    filenames = glob.glob('image*.png')
    filenames = sorted(filenames)
    last = -1
    for i,filename in enumerate(filenames):
        frame = 2*(i**0.5)
        if round(frame) > round(last):
            last = frame
        else:
            continue
        image = imageio.imread(filename)
        writer.append_data(image)
    image = imageio.imread(filename)
    writer.append_data(image)

import IPython
if IPython.version_info > (6,2,0,''):
    display.Image(filename=anim_file)

