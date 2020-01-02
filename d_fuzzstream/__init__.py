import pandas as pd
import numpy as np
from datetime import datetime

class SummaryStructure:
    def __init__(
        self, 
        min_fc=5, 
        max_fc=200, 
        threshold=1, 
        fuzziness=2):
        
        self.min_fc = min_fc
        self.max_fc = max_fc
        self.threshold = threshold
        self.fuzziness = fuzziness

        self.fclusters = set()

        self.test = False
        self.purity = 0
        self.creations = 0
        self.removals = 0
        self.absorptions = 0
        self.merges = 0
    
    def clustering(self, datastream, test = False):
        self.test = test
        for example in datastream.itertuples():
            i_example = tuple([example.x, example.y])
            if len(self.fclusters) < self.min_fc:
                fc = FMiC(i_example)
                self.fclusters.add(fc)
                if self.test: self.creations += 1
            else:
                all_dist = self.distances(i_example)
                is_outlier = True
                for i_fc in self.fclusters:
                    radius = 0
                    if i_fc.N == 1:
                        radius = self.min_distance(i_fc)
                    else:
                        radius = i_fc.fuzzy_dispersion()
                    if all_dist[i_fc] <= radius:
                        is_outlier = False
                        i_fc.timestamp = datetime.today().timestamp()
                if is_outlier:
                    if len(self.fclusters) == self.max_fc:
                        self.remove_oldest()
                        if self.test: self.removals += 1
                    fc = FMiC(i_example)
                    self.fclusters.add(fc)
                    if self.test: self.creations += 1
                else:
                    m_degrees = self.calc_m_degrees(all_dist)
                    self.update_fclusters(i_example, all_dist, m_degrees)
                    if self.test: self.absorptions += 1
                self.merge_fclusters()
        if self.test: self.evaluate_purity(datastream)
    
    def evaluate_purity(self, datastream):
        self.purity = 0
        for i_fc in self.fclusters:
            prototype = i_fc.prototype()
            radius = i_fc.fuzzy_dispersion()
            real_values = dict()
            max_value = 0
            for example in datastream.itertuples():
                i_example = tuple([example.x, example.y])
                dist = self.euclidean_distance(i_example, prototype)
                if dist < radius:
                    real_values[example.target] = real_values.get(example.target, 0) + 1
                    if real_values[example.target] > max_value:
                        max_value = real_values[example.target]
            self.purity += max_value
        self.purity = self.purity / datastream.shape[0]       

    def euclidean_distance(self, a, b):
        return (((a[0]-b[0])**2 + (a[1]-b[1])**2) ** (1/2))

    def min_distance(self, i_fc):
        res = 999999
        for j_fc in self.fclusters:
            if i_fc == j_fc: continue
            res = min(res, self.euclidean_distance(i_fc.prototype(), j_fc.prototype()))
        return res
    
    def distances(self, example):
        res = dict()
        for i_fc in self.fclusters:
            res[i_fc] = self.euclidean_distance(example, i_fc.prototype())
        return res

    def remove_oldest(self):
        min_timestamp = list(self.fclusters)[0].timestamp
        for i_fc in self.fclusters:
            min_timestamp = min(min_timestamp, i_fc.timestamp)
        for i_fc in self.fclusters:
            if i_fc.timestamp == min_timestamp:
                self.fclusters.remove(i_fc)
                return

    def calc_m_degrees(self, all_dist):
        m_degrees = dict()
        for i_fc in self.fclusters:
            i_dist = all_dist[i_fc]
            m_degree = 0
            for j_fc in self.fclusters:
                j_dist = all_dist[j_fc]
                m_degree += (i_dist/j_dist) ** (2./(self.fuzziness-1))
            m_degrees[i_fc] = 1. / m_degree
        return m_degrees

    def update_fclusters(self, i_example, all_dist, m_degrees):
        for i_fc in self.fclusters:
            m_degree = m_degrees[i_fc]
            dist = all_dist[i_fc]
            #i_fc.SSD += (m_degree**self.fuzziness) * (dist**2)
            i_fc.SSD += m_degree * (dist**2)
            i_fc.CF += np.array(i_example) * m_degree
            i_fc.N += 1
            i_fc.M += m_degree

    def merge_fclusters(self):
        merge = False
        for i_fc in self.fclusters:
            if merge: break
            similarity = 0
            for j_fc in self.fclusters:
                if i_fc == j_fc: continue
                similarity = self.similarity(i_fc, j_fc)
                if similarity > self.threshold:
                    merge = True
                    i_fc.N += j_fc.N
                    i_fc.M += j_fc.M
                    i_fc.SSD += j_fc.SSD
                    i_fc.CF += j_fc.CF
                    break
        if merge:
            self.fclusters.remove(j_fc)
            if self.test: self.merges += 1

    def similarity(self, i_fc, j_fc):
        similarity = 0
        sum_radius = i_fc.fuzzy_dispersion() + j_fc.fuzzy_dispersion()
        dist = self.euclidean_distance(i_fc.prototype(), j_fc.prototype())
        similarity = sum_radius / dist
        return similarity

    def to_dataframe(self):
        data = {'x': [], 'y': [], 'radius': [], 'N': [], 'M': [], 'SSD': [], 'CF': []}
        for i_fc in self.fclusters:
            prototype = i_fc.prototype()
            data['x'].append(prototype[0])
            data['y'].append(prototype[1])
            data['N'].append(i_fc.N)
            data['M'].append(i_fc.M)
            data['SSD'].append(i_fc.SSD)
            data['CF'].append(i_fc.CF)
            if i_fc.N == 1:
                data['radius'].append(self.min_distance(i_fc))
            else:
                data['radius'].append(i_fc.fuzzy_dispersion())
        return pd.DataFrame(data)

class FMiC:
    def __init__(self, example):
        self.N = 1
        self.M = 1
        self.SSD = 0
        self.CF = example
        self.timestamp = datetime.today().timestamp()
    
    def fuzzy_dispersion(self):
        return (self.SSD / self.N) ** (1/2)

    def prototype(self):
        return np.array(self.CF) / self.M