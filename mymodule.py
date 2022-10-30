from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def one_hot_split(
        path='./data/train.csv',
        one_cat=[],
        display_columns=True,
        test_size=0.3):
    from sklearn.model_selection import train_test_split

    # データを読み込む関数
    df = pd.read_csv(path)
    cats = ['ChestPainType', 'RestingECG', 'ST_Slope']

    # 指定されたものをワンホット化
    if one_cat != []:
        df_cat = df[one_cat]
        oned_cat = pd.get_dummies(df_cat)
        df = pd.concat((df, oned_cat), axis=1)

    # 説明変数と目的変数を分割
    x = df.drop(cats + ['HeartDisease'], axis=1)
    y = df.HeartDisease
    # ワンホット化した説明位変数を表示
    if display_columns:
        print('-'*15, f' {one_cat}をエンコード', '-'*15)
        display(x)
    # 訓練データと検証データをホールドアウトで分割
    x_train, x_test, y_train, y_test = train_test_split(
                                                        x, y,
                                                        test_size=test_size,
                                                        shuffle=True,
                                                        random_state=42
                                                        )
    return x_train, x_test, y_train, y_test


class PipeLine(object):
    def __init__(self):
        """アトリビュートで訓練データ、正解データを管理する
        df: callメソッドでオリジナルのデータが格納される
        df_num: callで指定した数値データ。クラスメソッドで上書きされる
        df_cat: callで指定したカテゴリデータ。クラスメソッドで上書きされる
        viewer: bool, viewer_row :int 更新後のデータを表示する
        """
        self.df: pd.DataFrame = None
        self.df_num: pd.DataFrame = None
        self.df_cat: pd.DataFrame = None
        self.df_target: pd.DataFrame = None
        self.viewer = True  # 更新したカラムの表示を切り替え
        self.viewer_row = 3  # 表示カラムの行数
        self.random_seed = 42  # 乱数シード値

    def __call__(self,
                 data: pd.DataFrame,
                 numerical=['Age', 'Sex', 'RestingBP', 'Cholesterol', \
                 'FastingBS', 'MaxHR', 'ExerciseAngina', 'Oldpeak'],
                 categorical=['ChestPainType', 'RestingECG', 'ST_Slope'],
                 target=['HeartDisease'],
                 train_flg=True
                 ) -> pd.DataFrame:

        self.df = data
        self.df_num = data[numerical]
        self.df_cat = data[categorical]
        # 正解ラベルが与えられない本番環境では引数からFalseにすること
        if train_flg:
            self.df_target = data[target]
        return None

    def standard_scaler(self):
        """アトリビュートのdf_numを標準化する
        view: 標準化したdf_numを確認できる
        """
        columns = self.df_num.columns
        scaler = StandardScaler()
        scaler.fit(self.df_num)
        self.df_num = scaler.transform(self.df_num)
        self.df_num = pd.DataFrame(self.df_num, columns=columns)
        if self.viewer:
            print('-'*20, '標準化されたdf_num', '-'*20)
            display(self.df_num.head(self.viewer_row))
        return None

    def one_hot(self,
                columns: list[str],
                concat=True) -> pd.DataFrame:
        """指定したカテゴリをワンホットして返し、アトリビュートの更新を行う
        columns: ワンホット化したいカラム名を指定する
        concat: Trueの場合はアトリビュートのself.df_numに連結し更新する
        view: ワンホットされたデータがdf_numにconcatされているのを確認できる
        """
        one_hotted = pd.get_dummies(self.df_cat[columns])
        self.df_num = pd.concat((self.df_num, one_hotted), axis=1)
        if self.viewer:
            print('-'*20, f'ワンホットされたカラム{columns}', '-'*20)
            display(self.df_num.head(self.viewer_row))
        return one_hotted

    def fold_out_split(self, test_size=0.3) -> np.ndarray:
        x_tr, x_te, y_tr, y_te = train_test_split(self.df_num,  self.df_target,
                                                  test_size=test_size,
                                                  random_state=self.random_seed)
        if self.viewer:
            print('-'*20, '分割されたデータShape', '-'*20)
            print(f'x_train: {x_tr.shape} x_test: {x_te.shape}')
            print(f'y_train: {y_tr.shape} y_test: {y_te.shape}')
        return x_tr.values, x_te.values, y_tr.values, y_te.values
