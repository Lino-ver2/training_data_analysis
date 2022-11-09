from __future__ import annotations
import pickle

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.model_selection import KFold
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, \
                            recall_score, f1_score


class PipeLine(object):
    """
    __init__ :
    アトリビュートで訓練データ、正解データを管理する
    （引数）
    df: callメソッドでオリジナルのデータが格納される
    df_num: callで指定した数値データが格納される。クラスメソッドで上書きされる
    df_cat: callで指定したカテゴリデータが格納される
    viewer: bool, viewer_row :int 更新後のデータを表示する

    __call__ :
    インスタンスの生成時に引数でオリジナルデータを渡す
    （引数）
    data: 使用するオリジナルデータ  (pd.DataFrame)
    numerical: 数値データのカラム名  (list[str])
    categorical: カテゴリデータのカラム名  (list[str])
    target:
    """

    def __init__(self, train_flg=True):
        self.df: pd.DataFrame = None
        self.df_num: pd.DataFrame = None
        self.df_cat: pd.DataFrame = None
        self.df_target: pd.DataFrame = None
        self.train_flg = train_flg  # 正解ラベルのないテストデータはFalseを設定
        self.viewer = False  # 更新したカラムの表示を切り替え
        self.viewer_row = 5  # 表示カラムの行数
        self.random_seed = 42  # 乱数シード値

    def __call__(self, data: pd.DataFrame, target='HeartDisease') -> pd.DataFrame:
        if self.train_flg:
            df = data.copy().drop(target, axis=1)
        else:
            df = data.copy()
        num, cat = [], []
        for column in df.columns:
            if df.dtypes[column] == 'O':
                cat.append(column)
            else:
                num.append(column)
        
        self.df = data
        self.df_num = data[num]
        self.df_cat = data[cat]
        # 正解ラベルが与えられない本番環境では引数からFalseにすること
        if self.train_flg:
            self.df_target = data[target]
        return self.df_num

    def standard_scaler(self):
        columns = self.df_num.columns
        scaler = StandardScaler()
        scaler.fit(self.df_num)
        self.df_num = scaler.transform(self.df_num)
        self.df_num = pd.DataFrame(self.df_num, columns=columns)
        if self.viewer:
            print('-'*20, '標準化されたdf_num', '-'*20)
            display(self.df_num.head(self.viewer_row))
        return None

    def one_hot(self, columns: list[str]) -> pd.DataFrame:
        one_hotted = pd.get_dummies(self.df_cat[columns]).reset_index(drop=True)
        self.df_num = pd.concat((self.df_num, one_hotted), axis=1)
        if self.viewer:
            print('-'*20, f'ワンホットされたカラム{columns}', '-'*20)
            display(self.df_num.head(self.viewer_row))
        return None


    def fold_out_split(self, test_size=0.3, to_array=False) -> np.ndarray:
        pack = train_test_split(self.df_num,  self.df_target,
                                test_size=test_size,
                                random_state=self.random_seed)
        x_tr, x_te, y_tr, y_te = pack
        if to_array:
            x_tr, x_te, y_tr, y_te = [i.values for i in pack]
            y_tr, y_te = y_tr.reshape(-1), y_te.reshape(-1)
        if self.viewer:
            print('-'*20, '分割されたデータShape', '-'*20)
            print(f'x_train: {x_tr.shape} x_test: {x_te.shape}')
            print(f'y_train: {y_tr.shape} y_test: {y_te.shape}')
        return x_tr, x_te, y_tr, y_te

    def k_fold(self, n_splits=5, to_array=True) -> list[list[np.ndarray]]:
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=self.random_seed)
        packs = []
        for train_index, test_index in kf.split(self.df_num):
            x_tr, x_te = self.df_num.iloc[train_index],\
                         self.df_num.iloc[test_index]
            y_tr, y_te = self.df_target.iloc[train_index],\
                         self.df_target.iloc[test_index]
            pack = (x_tr, x_te,  y_tr, y_te)
            if to_array:
                pack = [unpack.values for unpack in pack]
            packs.append(pack)
        if self.viewer:
            print(kf.get_n_splits)
        return packs

    def training(self, valid, model, valid_args={}, params={}, view=True):
        if view:
            print('-'*20, '使用された特徴量', '-'*20)
            display(self.df_num.head(self.viewer_row))

        if valid == 'fold_out_split':
            packs = self.fold_out_split(**valid_args)
            train_model = model(**params)
            train_model.fit(packs[0], packs[2])
            evaluations(train_model, *packs)
            return train_model

        if valid == 'k_fold':
            packs = self.k_fold(**valid_args)
            models = []
            for i, pack in enumerate(packs):
                train_model = model(**params)
                train_model.fit(pack[0], pack[2].reshape(-1))
                print('-'*20, f'model{i} predict', '-'*20)
                evaluations(train_model, *pack)
                models.append(train_model)
            return models


# 前処理
def df_copy(df, func, columns):
    df_c = df.copy()
    df_c[columns] = func
    return df_c


def train_or_test(pipe, train_flg, split_kwrg={}):
    if train_flg:
        pack = pipe.fold_out_split(**split_kwrg)
        return pack
    else:
        return pipe.df_num


# グリッドサーチの関数
def grid_search_cv(pack, param_grid, model, model_arg={}, score='accuracy'):
    gs_model = GridSearchCV(estimator=model(**model_arg),
                            param_grid=param_grid,  # 設定した候補を代入
                            scoring=score,  # デフォルトではaccuracyを基準に探してくれる
                            refit=True,
                            cv=3,
                            n_jobs=-1)
    # 訓練データで最適なパラメータを交差検証する
    if model.__name__ == 'XGBClassifier':  # early_stoppingのためにeval_setを用意
        eval_set = [(pack[1], pack[3])]  # x_train, x_test, y_train, y_test = pack
        gs_model.fit(pack[0], pack[2], eval_set=eval_set, verbose=False)
    else:
        gs_model.fit(pack[0], pack[2])
    evaluations(gs_model, *pack)
    return gs_model


# 評価指標の関数
def evaluations(model, x_train, x_test, y_train, y_test):
    evaluate = [accuracy_score, precision_score, recall_score, f1_score]
    # 訓練データの評価
    train_pred = model.predict(x_train)
    train_val = {func.__name__: func(y_train, train_pred) for func in evaluate}
    # 検証データの評価
    test_pred = model.predict(x_test)
    test_val = {func.__name__: func(y_test, test_pred) for func in evaluate}
    evals = pd.DataFrame((train_val, test_val), index=['train', 'test'])
    print('-'*20, '評価結果', '-'*20)
    display(evals)
    return evals


# K_foldによる予測
def k_fold_prediction(models, x):
    try:
        predict = [model.predict_proba(x) for model in models]
        predict_sum = np.sum(predict, axis=0)
        ensemble_prediction = np.array(
            [np.where(pre[0] < pre[1], 1, 0) for pre in predict_sum]
            )
    except AttributeError:
        print('########## 確率で出力するようパラメータもしくはモデルを選択することを推奨 ############')
        predict = [model.predict(x) for model in models]
        predict_sum = np.sum(predict, axis=0)
        ensemble_prediction = np.array(
                [np.where(len(models)//2 <= pre, 1, 0) for pre in predict_sum]
                )
    return ensemble_prediction


# 予測値を入力して評価する関数
def ensemble_evals(ensemble_pred, target):
    evaluate = [accuracy_score, precision_score, recall_score, f1_score]
    # 訓練データの評価
    ensemble = {func.__name__: func(target, ensemble_pred) for func in evaluate}
    evals = pd.DataFrame((ensemble), index=['ensemble'])
    print('-'*20, 'ensemble', '-'*20)
    display(evals)
    return None


# 最適パラメータでの再訓練用関数
def best_parameters(train_models, pipe_lines):
    parameters = {}
    for key in train_models.keys():
        model = train_models[key]
        best_params = {}
        for pipe in pipe_lines:
            try:
                best = model[pipe.__name__].best_params_
                best_params[pipe.__name__] = best
            except KeyError:
                pass
        parameters[key] = best_params
    return parameters


def retrained(retrain, pipe_lines, data_set, best_param, file_name):
    retrained = {}
    for re_tr in retrain:
        retrained[re_tr.__name__] = {}
        for pipe in pipe_lines:
            x, y = data_set[pipe.__name__]
            try:
                param = best_param[re_tr.__name__][pipe.__name__]
                model = re_tr(**param)
                model.fit(x.values, y.values.reshape(-1))
                retrained[re_tr.__name__][pipe.__name__] = model
                with open(f'./data/retrained_{file_name}.pkl', 'wb') as f:
                    pickle.dump(retrained, f)
            except KeyError:
                pass
    return retrained


# サブミット用の評価関数
def test_eval(train_models, pipe_lines, data_set, y):
    predicts = {}
    for key in train_models.keys():
        if train_models[key] != {}:
            model = train_models[key]
            scores = []
            index = []
            for pipe in pipe_lines:
                try:
                    x = data_set[pipe.__name__]
                    pred = model[pipe.__name__].predict(x)
                    score = accuracy_score(y.values, pred)
                    scores.append(score)
                    index.append(pipe.__name__)
                except KeyError:
                    pass
            predicts[key] = scores
        else:
            pass
    return pd.DataFrame(predicts, index=index)